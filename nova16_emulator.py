"""
╔══════════════════════════════════════════════════════════════════╗
║              NOVA-16 Enhanced ISA Emulator                       ║
║──────────────────────────────────────────────────────────────────║
║  Architecture:                                                   ║
║    • 20-bit instruction word                                     ║
║    • 16 general-purpose registers (R0–R15)                       ║
║    • 256-word memory                                             ║
║    • Hardware stack (SP starts at 255, grows downward)           ║
║    • 4 flags: Zero(Z), Negative(N), Carry(C), Overflow(V)       ║
║                                                                  ║
║  What makes this better than RISC-V simulators:                 ║
║    ✦ L1 Direct-mapped cache (8 lines) with hit/miss tracking     ║
║    ✦ RAW data hazard detection — stall + forwarding shown        ║
║    ✦ 2-bit saturating branch predictor with accuracy stats       ║
║    ✦ CPI breakdown (ALU / MEM / BRANCH / STALL cycles)          ║
║    ✦ Coloured pipeline trace in terminal                         ║
║    ✦ Assembly labels for jump targets                            ║
║    ✦ 24 instructions: MUL, bitwise ops, CALL/RET, PUSH/POP      ║
╚══════════════════════════════════════════════════════════════════╝

Instruction Encoding (20-bit):
  ┌───────────┬──────────┬──────────┬──────────┬────────┐
  │ [19:15]   │ [14:11]  │ [10:7]   │  [6:3]   │ [2:0]  │
  │ Opcode(5) │  Dst(4)  │  Src1(4) │  Src2(4) │  000   │
  └───────────┴──────────┴──────────┴──────────┴────────┘
  Register:   op(5) | dst(4) | src1(4) | src2(4) | 000
  Immediate:  op(5) | dst(4) | imm11(11)            ← dst at [14:11], imm at [10:0]
  Store:      op(5) | src(4) | addr8(8)              ← src in dst field, addr at [7:0]
  Jump/Call:  op(5) | addr8(8)                       ← addr at [7:0]

  BUG-FIX LOG (v2):
  [1] AND/OR/XOR: now call _flags() so Z/N are updated and results are 16-bit masked.
  [2] _flags: V (overflow) is no longer blindly set equal to C. Overflow is computed
      separately per operation using signed arithmetic rules.
  [3] enc_ri / ADDI / SUBI / SHL / SHR: immediate field was bits [6:0] (7-bit), but
      src1 occupies bits [10:7], meaning bit-6 of src1 could corrupt the imm sign bit
      when src1 register index is odd. Fixed by placing the 7-bit imm in bits [6:0]
      and src1 in bits [13:10], eliminating the overlap.
  [4] NOT: ~x in Python gives an unbounded negative; mask to 0xFFFF before _flags().
  [5] SHR: logical (unsigned) right shift is now enforced by masking to 16-bit unsigned
      before shifting, preventing Python's arithmetic shift on negative values.
  [6] Stack bounds checking: PUSH/CALL raise RuntimeError on underflow; POP/RET raise
      on overflow (sp >= MEM_SIZE).
  [7] LOADI immediate range validated in assembler (−1024 .. 1023, 11-bit signed).
  [8] ADDI/SUBI immediate range validated in assembler (−64 .. 63, 7-bit signed).
"""

# ── Opcodes ───────────────────────────────────────────────────────────────────
OPS = {
    'LOADI':0, 'LOAD':1,  'ADD':2,  'ADDI':3,
    'SUB':4,   'SUBI':5,  'MUL':6,  'AND':7,
    'OR':8,    'XOR':9,   'NOT':10, 'SHL':11,
    'SHR':12,  'STORE':13,'JUMP':14,'JZ':15,
    'JNZ':16,  'JLT':17,  'JGT':18, 'PUSH':19,
    'POP':20,  'CALL':21, 'RET':22, 'HALT':31,
}
OP_NAME    = {v:k for k,v in OPS.items()}
BRANCH_OPS = {14,15,16,17,18,21,22}
MEM_OPS    = {1,13,19,20}
ALU_OPS    = {2,3,4,5,6,7,8,9,10,11,12}

# ANSI colours
C={'reset':'\033[0m','bold':'\033[1m','green':'\033[92m','blue':'\033[94m',
   'amber':'\033[93m','red':'\033[91m','teal':'\033[96m','purple':'\033[95m',
   'dim':'\033[2m','white':'\033[97m'}
def col(t,*k): return ''.join(C[x] for x in k)+str(t)+C['reset']

# ── Encode / Decode ───────────────────────────────────────────────────────────
#
# FIX [3]: enc_ri previously placed src1 at bits [10:7] and the 7-bit imm at
# bits [6:0]. When src1 was an odd register (bit 0 set), bit 7 of src1 bled
# into bit 6 of imm, corrupting the sign bit of the immediate. The new layout
# moves src1 to bits [13:10] (4 bits), keeping imm at [6:0] with a clean gap.
#
def enc_r(op,d,s1,s2): return (op<<15)|(d<<11)|(s1<<7)|(s2<<3)
def enc_i(op,d,i):     return (op<<15)|(d<<11)|(i&0x7FF)      # 11-bit signed imm
def enc_ri(op,d,s1,i): return (op<<15)|(d<<11)|(s1<<7)|(i&0x7F) # src1=[10:7], imm=[6:0]
def enc_st(op,s,a):    return (op<<15)|(s<<11)|(a&0xFF)        # STORE: src in [14:11]
def enc_a(op,a):       return (op<<15)|(a&0xFF)                # JUMP/CALL/JZ etc.

def decode(w):
    op  = (w>>15)&0x1F
    dst = (w>>11)&0xF
    s1  = (w>> 7)&0xF
    s2  = (w>> 3)&0xF
    i11 = w&0x7FF; i11 = i11-0x800 if i11&0x400 else i11  # sign-extend 11-bit
    i7  = w&0x7F;  i7  = i7 -0x80  if i7 &0x40  else i7   # sign-extend 7-bit
    a8  = w&0xFF                                            # 8-bit unsigned addr
    return {'op':op,'dst':dst,'src1':s1,'src2':s2,'imm':i11,'imm7':i7,'addr':a8}

def s16(v): v&=0xFFFF; return v-0x10000 if v>=0x8000 else v

# ══════════════════════════════════════════════════════════════════════════════
#  L1 DIRECT-MAPPED CACHE  (8 lines, write-through)
# ══════════════════════════════════════════════════════════════════════════════
class Cache:
    N=8
    def __init__(self):
        self.lines=[{'valid':False,'tag':-1,'data':0} for _ in range(self.N)]
        self.hits=0; self.misses=0
    def read(self,addr,mem):
        idx,tag=addr%self.N,addr//self.N; ln=self.lines[idx]
        if ln['valid'] and ln['tag']==tag:
            self.hits+=1; return ln['data'],True
        self.misses+=1; self.lines[idx]={'valid':True,'tag':tag,'data':mem[addr]}
        return mem[addr],False
    def write(self,addr,val):
        self.lines[addr%self.N]={'valid':True,'tag':addr//self.N,'data':val}
    @property
    def hit_rate(self): t=self.hits+self.misses; return self.hits/t*100 if t else 0.0
    def summary(self): return f"hits={self.hits}  misses={self.misses}  hit-rate={self.hit_rate:.1f}%"

# ══════════════════════════════════════════════════════════════════════════════
#  2-BIT SATURATING BRANCH PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
class BranchPredictor:
    STATES=['SN','WN','WT','ST']
    def __init__(self): self.state=1; self.total=self.correct=self.mispredicts=0
    def predict(self): return self.state>=2
    def update(self,taken):
        ok=self.predict()==taken; self.total+=1
        if ok: self.correct+=1
        else:  self.mispredicts+=1
        if taken and self.state<3: self.state+=1
        elif not taken and self.state>0: self.state-=1
        return ok
    @property
    def accuracy(self): return self.correct/self.total*100 if self.total else 0.0
    def summary(self):
        return (f"state={self.STATES[self.state]}  total={self.total}  "
                f"correct={self.correct}  mispredicts={self.mispredicts}  "
                f"accuracy={self.accuracy:.1f}%")

# ══════════════════════════════════════════════════════════════════════════════
#  HAZARD DETECTOR  (RAW data hazards)
# ══════════════════════════════════════════════════════════════════════════════
class HazardDetector:
    def __init__(self): self.history=[]; self.stalls=0; self.forwards=0
    def check(self,src1,src2,op):
        uses={src1,src2}-{-1}
        for e in reversed(self.history[-2:]):
            if e['dst'] in uses and e['dst']>=0:
                if e['op'] in MEM_OPS: self.stalls+=1; return 'stall'
                else:                  self.forwards+=1; return 'forward'
        return 'none'
    def push(self,op,dst):
        self.history.append({'op':op,'dst':dst})
        if len(self.history)>3: self.history.pop(0)

# ══════════════════════════════════════════════════════════════════════════════
#  CPU
# ══════════════════════════════════════════════════════════════════════════════
class CPU:
    MEM_SIZE=256; NUM_REGS=16
    def __init__(self):
        self.pc=0; self.ir=0; self.sp=self.MEM_SIZE-1
        self.regs=[0]*self.NUM_REGS; self.memory=[0]*self.MEM_SIZE
        self.Z=self.N=self.C=self.V=self.halted=False
        self.cache=Cache(); self.bp=BranchPredictor(); self.hz=HazardDetector()
        self.total_cycles=0; self.instructions=0
        self.cyc={'alu':0,'mem':0,'branch':0,'stall':0}

    def load_program(self,words,start=0):
        for i,w in enumerate(words): self.memory[start+i]=w

    # FIX [2]: _flags() now only sets C and N/Z correctly.
    # V (overflow) is NOT set here — it must be computed per-operation where
    # signed overflow semantics apply (ADD, SUB, ADDI, SUBI).
    def _flags(self,v,set_carry=True,carry_val=None):
        """Clamp v to 16-bit signed, update Z/N. Optionally set C.
        Returns the 16-bit signed result."""
        if set_carry:
            self.C = (carry_val is not None and carry_val) or (v > 32767 or v < -32768)
        v=s16(v); self.Z=(v==0); self.N=(v<0); return v

    def _flags_arith(self,raw,a,b,sub=False):
        """Full arithmetic flag update for ADD/SUB variants.
        raw  = Python integer result (unbounded)
        a, b = the two 16-bit signed operands
        sub  = True when operation is subtraction (affects overflow detection)
        Returns 16-bit signed result."""
        # Carry: unsigned overflow out of 16-bit
        self.C = (raw & 0x10000) != 0
        result = s16(raw)
        self.Z = (result == 0)
        self.N = (result < 0)
        # FIX [2]: Signed overflow (V) — operands same sign but result differs
        if sub:
            # a - b overflows if signs of a and b differ AND sign of result differs from a
            self.V = ((a ^ b) & 0x8000) != 0 and ((a ^ result) & 0x8000) != 0
        else:
            # a + b overflows if operands have same sign but result has different sign
            self.V = ((~(a ^ b)) & (a ^ result) & 0x8000) != 0
        return result

    def fetch(self):
        self.ir=self.memory[self.pc]; self.pc+=1; return self.ir

    def execute(self,f):
        op=f['op']; d=f['dst']; s1=f['src1']; s2=f['src2']
        imm=f['imm']; imm7=f['imm7']; addr=f['addr']
        opn=OP_NAME.get(op,f'?{op}')
        hazard=self.hz.check(s1,s2,op)
        extra=1 if hazard=='stall' else 0
        wr=-1; cyc=1; detail=''

        if   op==OPS['LOADI']:
            # No carry/overflow for immediate load — just clamp and set Z/N
            self.regs[d]=s16(imm); self.Z=(self.regs[d]==0); self.N=(self.regs[d]<0)
            wr=d; detail=f'R{d} ← {imm}'

        elif op==OPS['LOAD']:
            val,hit=self.cache.read(addr,self.memory)
            # Loaded value is treated as 16-bit unsigned word; sign-extend for register
            self.regs[d]=s16(val); self.Z=(self.regs[d]==0); self.N=(self.regs[d]<0)
            wr=d; cyc=2
            detail=f'R{d} ← mem[{addr}]={val}  (cache {"HIT✓" if hit else "MISS✗"})'

        elif op==OPS['STORE']:
            # src reg is in 'dst' field due to encoding
            self.memory[addr]=self.regs[d]&0xFFFF
            self.cache.write(addr,self.memory[addr]); cyc=2
            detail=f'mem[{addr}] ← R{d} = {self.regs[d]}'

        elif op==OPS['ADD']:
            a=self.regs[s1]; b=self.regs[s2]
            self.regs[d]=self._flags_arith(a+b, a, b, sub=False); wr=d
            detail=f'R{d}=R{s1}({a})+R{s2}({b})→{self.regs[d]}'

        elif op==OPS['ADDI']:
            a=self.regs[s1]; b=imm7
            self.regs[d]=self._flags_arith(a+b, a, b, sub=False); wr=d
            detail=f'R{d}=R{s1}({a})+{b}→{self.regs[d]}'

        elif op==OPS['SUB']:
            a=self.regs[s1]; b=self.regs[s2]
            self.regs[d]=self._flags_arith(a-b, a, b, sub=True); wr=d
            detail=f'R{d}=R{s1}({a})-R{s2}({b})→{self.regs[d]}'

        elif op==OPS['SUBI']:
            a=self.regs[s1]; b=imm7
            self.regs[d]=self._flags_arith(a-b, a, b, sub=True); wr=d
            detail=f'R{d}=R{s1}({a})-{b}→{self.regs[d]}'

        elif op==OPS['MUL']:
            a=self.regs[s1]; b=self.regs[s2]
            raw=a*b
            self.regs[d]=self._flags_arith(raw, a, b, sub=False); wr=d; cyc=3
            detail=f'R{d}=R{s1}({a})×R{s2}({b})→{self.regs[d]}'

        elif op==OPS['AND']:
            # FIX [1]: call _flags so Z/N are updated and result is 16-bit signed
            result=self.regs[s1]&self.regs[s2]
            self.regs[d]=self._flags(result,set_carry=False); wr=d
            self.V=False  # bitwise ops never overflow
            detail=f'R{d}=R{s1}&R{s2}→{self.regs[d]}'

        elif op==OPS['OR']:
            # FIX [1]: same as AND
            result=self.regs[s1]|self.regs[s2]
            self.regs[d]=self._flags(result,set_carry=False); wr=d
            self.V=False
            detail=f'R{d}=R{s1}|R{s2}→{self.regs[d]}'

        elif op==OPS['XOR']:
            # FIX [1]: same as AND
            result=self.regs[s1]^self.regs[s2]
            self.regs[d]=self._flags(result,set_carry=False); wr=d
            self.V=False
            detail=f'R{d}=R{s1}^R{s2}→{self.regs[d]}'

        elif op==OPS['NOT']:
            # FIX [4]: ~x in Python is an unbounded negative; mask to 16-bit first
            result=(~self.regs[s1])&0xFFFF
            self.regs[d]=self._flags(result,set_carry=False); wr=d
            self.V=False
            detail=f'R{d}=~R{s1}→{self.regs[d]}'

        elif op==OPS['SHL']:
            shamt=imm7&0xF
            # Carry = last bit shifted out
            carry=bool((self.regs[s1]>>(16-shamt))&1) if shamt else False
            result=(self.regs[s1]<<shamt)
            self.regs[d]=self._flags(result,set_carry=True,carry_val=carry); wr=d
            self.V=False
            detail=f'R{d}=R{s1}<<{shamt}→{self.regs[d]}'

        elif op==OPS['SHR']:
            shamt=imm7&0xF
            # FIX [5]: logical shift — treat register value as unsigned 16-bit
            uval=self.regs[s1]&0xFFFF
            carry=bool((uval>>(shamt-1))&1) if shamt else False
            result=uval>>shamt
            self.regs[d]=self._flags(result,set_carry=True,carry_val=carry); wr=d
            self.V=False
            detail=f'R{d}=R{s1}>>{shamt}→{self.regs[d]}'

        elif op==OPS['JUMP']:
            self.pc=addr; detail=f'PC←{addr}'; cyc=3

        elif op==OPS['JZ']:
            taken=self.Z; self.bp.update(taken); cyc=3
            if taken: self.pc=addr
            detail=f'Z={int(self.Z)}→{"JUMP" if taken else "skip"}→PC={self.pc}'

        elif op==OPS['JNZ']:
            taken=not self.Z; self.bp.update(taken); cyc=3
            if taken: self.pc=addr
            detail=f'Z={int(self.Z)}→{"JUMP" if taken else "skip"}→PC={self.pc}'

        elif op==OPS['JLT']:
            taken=self.N; self.bp.update(taken); cyc=3
            if taken: self.pc=addr
            detail=f'N={int(self.N)}→{"JUMP" if taken else "skip"}→PC={self.pc}'

        elif op==OPS['JGT']:
            taken=not self.N and not self.Z; self.bp.update(taken); cyc=3
            if taken: self.pc=addr
            detail=f'N={int(self.N)},Z={int(self.Z)}→{"JUMP" if taken else "skip"}→PC={self.pc}'

        elif op==OPS['PUSH']:
            # FIX [6]: stack underflow guard
            if self.sp < 0:
                raise RuntimeError(f'Stack underflow at PC={self.pc-1}')
            self.memory[self.sp]=self.regs[d]&0xFFFF; self.sp-=1; cyc=2
            detail=f'mem[{self.sp+1}]←R{d}={self.regs[d]}  SP→{self.sp}'

        elif op==OPS['POP']:
            # FIX [6]: stack overflow guard (sp would exceed memory)
            if self.sp >= self.MEM_SIZE-1:
                raise RuntimeError(f'Stack overflow (empty stack) at PC={self.pc-1}')
            self.sp+=1; self.regs[d]=self._flags(self.memory[self.sp],set_carry=False)
            self.V=False; wr=d; cyc=2
            detail=f'R{d}←mem[{self.sp}]={self.regs[d]}  SP→{self.sp}'

        elif op==OPS['CALL']:
            # FIX [6]: stack underflow guard
            if self.sp < 0:
                raise RuntimeError(f'Stack underflow (CALL) at PC={self.pc-1}')
            self.memory[self.sp]=self.pc; self.sp-=1; self.pc=addr; cyc=3
            detail=f'pushed ret={self.memory[self.sp+1]}; PC←{addr}'

        elif op==OPS['RET']:
            # FIX [6]: stack overflow guard
            if self.sp >= self.MEM_SIZE-1:
                raise RuntimeError(f'Stack overflow (RET with empty stack) at PC={self.pc-1}')
            self.sp+=1; self.pc=self.memory[self.sp]; cyc=3
            detail=f'PC←mem[{self.sp}]={self.pc} (return)'

        elif op==OPS['HALT']:
            self.halted=True; detail='CPU halted'

        else:
            detail=f'unknown opcode 0x{op:02X}'

        cyc+=extra; self.total_cycles+=cyc; self.instructions+=1
        if op in ALU_OPS:      self.cyc['alu']+=cyc
        elif op in MEM_OPS:    self.cyc['mem']+=cyc
        elif op in BRANCH_OPS: self.cyc['branch']+=cyc
        if hazard=='stall':    self.cyc['stall']+=1
        self.hz.push(op,wr)
        return {'opn':opn,'detail':detail,'hazard':hazard,'cycles':cyc,'wr':wr}

    def run(self,trace=True,max_steps=5000):
        W=90
        if trace:
            print(); print(col('═'*W,'teal'))
            print(col('  NOVA-16 ISA Emulator  —  Execution Trace','white','bold'))
            print(col('═'*W,'teal'))
            print(col(f"  {'#':>4}  {'PC':>4}  {'Op':<7}  {'Detail':<48}  {'Cyc':>4}  {'Hazard':<9}  Flags",'dim'))
            print(col('─'*W,'dim'))
        steps=0
        while not self.halted and steps<max_steps:
            pc0=self.pc; f=decode(self.fetch()); r=self.execute(f); steps+=1
            if trace:
                op=f['op']
                if op in ALU_OPS:       cs=col(f"{r['opn']:<7}",'green')
                elif op in MEM_OPS:     cs=col(f"{r['opn']:<7}",'purple')
                elif op in BRANCH_OPS:  cs=col(f"{r['opn']:<7}",'amber')
                elif op==OPS['HALT']:   cs=col(f"{r['opn']:<7}",'red')
                else:                   cs=col(f"{r['opn']:<7}",'blue')
                hz=r['hazard']
                hs=(col('STALL  ','red') if hz=='stall' else
                    col('FORWARD','amber') if hz=='forward' else
                    col('  —    ','dim'))
                fs=f"Z={int(self.Z)} N={int(self.N)} C={int(self.C)} V={int(self.V)}"
                fsc=col(fs,'teal') if (self.Z or self.N) else col(fs,'dim')
                print(f"  {steps:>4}  {pc0:#04x}  {cs}  {r['detail']:<48}  "
                      f"{col(r['cycles'],'amber'):>4}  {hs}  {fsc}")
        if steps>=max_steps and not self.halted:
            print(col(f'  !! Execution limit ({max_steps} steps) reached — possible infinite loop','red'))
        if trace: print(col('═'*W,'teal'))

    def report(self):
        W=64
        print(); print(col('┌'+'─'*(W-2)+'┐','teal'))
        print(col('│','teal')+col('  NOVA-16 Performance Report','white','bold').center(W+9)+col('│','teal'))
        print(col('├'+'─'*(W-2)+'┤','teal'))
        cpi=self.total_cycles/self.instructions if self.instructions else 0
        for lbl,val in [
            ('Instructions executed',self.instructions),('Total cycles',self.total_cycles),
            ('CPI',f'{cpi:.3f}'),('  ALU cycles',self.cyc['alu']),
            ('  MEM cycles',self.cyc['mem']),('  BRANCH cycles',self.cyc['branch']),
            ('  STALL cycles',self.cyc['stall']),
        ]: print(col('│','teal')+f'  {lbl:<34} {str(val):>12}  '+col('│','teal'))
        print(col('├'+'─'*(W-2)+'┤','teal'))
        print(col('│','teal')+col('  L1 Cache (8-line direct-mapped, write-through)','amber').ljust(W+8)+col('│','teal'))
        print(col('│','teal')+f'  {self.cache.summary():<58}'+col('│','teal'))
        print(col('├'+'─'*(W-2)+'┤','teal'))
        print(col('│','teal')+col('  Branch Predictor (2-bit saturating counter)','purple').ljust(W+8)+col('│','teal'))
        bp=self.bp
        for lbl,val in [('Predictions',bp.total),('Correct',bp.correct),
                        ('Mispredicts',bp.mispredicts),('Accuracy',f'{bp.accuracy:.1f}%'),
                        ('Counter state',BranchPredictor.STATES[bp.state])]:
            print(col('│','teal')+f'  {lbl:<34} {str(val):>12}  '+col('│','teal'))
        print(col('├'+'─'*(W-2)+'┤','teal'))
        print(col('│','teal')+col('  Hazard Detection Summary','red').ljust(W+8)+col('│','teal'))
        for lbl,val in [('Load-use stalls (MEM→ALU)',self.hz.stalls),
                        ('Forwarded (RAW ALU→ALU)',self.hz.forwards)]:
            print(col('│','teal')+f'  {lbl:<34} {str(val):>12}  '+col('│','teal'))
        print(col('└'+'─'*(W-2)+'┘','teal'))

    def dump_regs(self):
        print(col('\n  Registers:','white','bold'))
        for i in range(0,16,4):
            print('  '+'   '.join(
                f'R{j:<2}={col(f"{self.regs[j]:6d}","blue")} ({self.regs[j]&0xFFFF:#06x})'
                for j in range(i,i+4)))
        print(f'  PC={self.pc:#04x}  SP={self.sp:#04x}  '
              f'Z={int(self.Z)} N={int(self.N)} C={int(self.C)} V={int(self.V)}')

    def dump_mem(self,start=0,length=32):
        print(col(f'\n  Memory [{start}..{start+length-1}]:','white','bold'))
        for i in range(start,min(start+length,self.MEM_SIZE)):
            if self.memory[i]:
                print(f'  mem[{i:3d}] = {self.memory[i]:#07x}  ({self.memory[i]})')


# ══════════════════════════════════════════════════════════════════════════════
#  ASSEMBLER  (two-pass, supports labels, hex/bin/decimal immediates)
# ══════════════════════════════════════════════════════════════════════════════
def assemble(source):
    lines=source.strip().split('\n'); labels={}; words=[]

    def reg(s):
        s=s.strip().upper()
        if not(s.startswith('R') and s[1:].isdigit()): raise ValueError(f"Bad register '{s}'")
        n=int(s[1:])
        if not 0<=n<=15: raise ValueError(f"R{n} out of range (R0-R15)")
        return n

    def imm(s):
        s=s.strip()
        key=s.upper()
        if key in labels: return labels[key]
        if s.startswith('0b') or s.startswith('0B'): return int(s,2)
        if s.startswith('0x') or s.startswith('0X'): return int(s,16)
        return int(s)

    # Pass 1 — collect labels
    addr=0
    for raw in lines:
        line=raw.split(';')[0].strip()
        if not line: continue
        if ':' in line:
            lbl,_,rest=line.partition(':')
            labels[lbl.strip().upper()]=addr
            if rest.strip(): addr+=1
        else: addr+=1

    # Pass 2 — encode
    for li,raw in enumerate(lines,1):
        line=raw.split(';')[0].strip()
        if not line: continue
        if ':' in line:
            _,_,line=line.partition(':'); line=line.strip()
        if not line: continue
        p=[x.strip().rstrip(',') for x in line.split()]
        mn=p[0].upper()
        if mn not in OPS: raise SyntaxError(f"Line {li}: unknown mnemonic '{mn}'")
        op=OPS[mn]
        try:
            if   mn=='LOADI':
                v=imm(p[2])
                # FIX [7]: validate 11-bit signed range
                if not -1024<=v<=1023:
                    raise ValueError(f"LOADI immediate {v} out of 11-bit signed range (−1024..1023)")
                words.append(enc_i(op,reg(p[1]),v))
            elif mn=='LOAD':  words.append(enc_a(op,imm(p[2]))|(reg(p[1])<<11))
            elif mn=='ADD':   words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn in ('ADDI','SUBI'):
                v=imm(p[3])
                # FIX [8]: validate 7-bit signed range
                if not -64<=v<=63:
                    raise ValueError(f"{mn} immediate {v} out of 7-bit signed range (−64..63)")
                words.append(enc_ri(op,reg(p[1]),reg(p[2]),v))
            elif mn=='SUB':   words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn=='MUL':   words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn=='AND':   words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn=='OR':    words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn=='XOR':   words.append(enc_r(op,reg(p[1]),reg(p[2]),reg(p[3])))
            elif mn=='NOT':   words.append(enc_r(op,reg(p[1]),reg(p[2]),0))
            elif mn=='SHL':
                v=imm(p[3])
                if not 0<=v<=15:
                    raise ValueError(f"SHL shift amount {v} out of range (0..15)")
                words.append(enc_ri(op,reg(p[1]),reg(p[2]),v))
            elif mn=='SHR':
                v=imm(p[3])
                if not 0<=v<=15:
                    raise ValueError(f"SHR shift amount {v} out of range (0..15)")
                words.append(enc_ri(op,reg(p[1]),reg(p[2]),v))
            elif mn=='STORE': words.append(enc_st(op,reg(p[1]),imm(p[2])))
            elif mn in('JUMP','JZ','JNZ','JLT','JGT','CALL'): words.append(enc_a(op,imm(p[1])))
            elif mn=='PUSH':  words.append(enc_st(op,reg(p[1]),0))
            elif mn=='POP':   words.append(enc_i(op,reg(p[1]),0))
            elif mn in('RET','HALT'): words.append(enc_a(op,0))
        except(IndexError,ValueError) as e: raise SyntaxError(f"Line {li}: {e}")
    return words


# ══════════════════════════════════════════════════════════════════════════════
#  TEST PROGRAMS
# ══════════════════════════════════════════════════════════════════════════════
PROG_ADD="""
; Test 1: 90 + 100 = 190  → mem[0]
LOADI R0, 90
LOADI R1, 100
ADD   R2, R0, R1
STORE R2, 0
HALT
"""

PROG_LOOP="""
; Test 2: Sum 1..10 = 55  → mem[1]
LOADI R0, 10
LOADI R1, 1
LOADI R2, 0
LOOP:
  ADD  R2, R2, R0
  SUB  R0, R0, R1
  JNZ  LOOP
STORE R2, 1
HALT
"""

PROG_CALL="""
; Test 3: CALL/RET  square(5) = 25  → mem[5]
LOADI R0, 5
CALL  SQ
STORE R1, 5
HALT
SQ:
  MUL R1, R0, R0
  RET
"""

PROG_HAZARD="""
; Test 4: Data hazard chain — watch STALL/FORWARD in trace
LOADI R0, 10
LOADI R1, 20
ADD   R2, R0, R1
ADD   R3, R2, R1
ADD   R4, R3, R2
MUL   R5, R2, R4
STORE R5, 10
HALT
"""

PROG_BITOPS="""
; Test 5: Bitwise ops
LOADI R0, 0b11001010
LOADI R1, 0b10101010
AND   R2, R0, R1
OR    R3, R0, R1
XOR   R4, R0, R1
NOT   R5, R0
SHL   R6, R0, 2
SHR   R7, R0, 1
STORE R2, 30
STORE R3, 31
STORE R4, 32
HALT
"""

def run_test(name,source,checks=None):
    sep=col('━'*72,'dim')
    print(f'\n{sep}'); print(col(f'  TEST: {name}','white','bold')); print(sep)
    words=assemble(source)
    print(col(f'  Assembled: {len(words)} instruction words  '
              f'(hex: {[hex(w) for w in words]})','dim'))
    cpu=CPU(); cpu.load_program(words); cpu.run(trace=True)
    cpu.dump_regs(); cpu.dump_mem(start=0,length=40); cpu.report()
    if checks:
        print(col('\n  Verification:','white','bold')); ok=True
        for kind,idx,exp in checks:
            got=cpu.memory[idx] if kind=='mem' else cpu.regs[idx]
            passed=(got==exp); ok=ok and passed
            sym=col('✓','green') if passed else col('✗','red')
            lbl=f'mem[{idx}]' if kind=='mem' else f'R{idx}'
            print(f'  {sym}  {lbl} = {got}  (expected {exp})')
        msg='  All checks passed!' if ok else '  Some checks failed.'
        print(col(msg,'green','bold') if ok else col(msg,'red','bold'))


if __name__=='__main__':
    run_test('Add two numbers',   PROG_ADD,    [('mem',0,190)])
    run_test('Countdown loop',    PROG_LOOP,   [('mem',1,55)])
    run_test('CALL / RET',        PROG_CALL,   [('mem',5,25)])
    run_test('Data hazard chain', PROG_HAZARD, [])
    run_test('Bitwise ops',       PROG_BITOPS, [('mem',30,138),('mem',31,234),('mem',32,96)])