from flask import Flask, request, jsonify, render_template
from nova16_emulator import CPU, assemble
from dotenv import load_dotenv
import urllib.request
import urllib.error
import json
import os

load_dotenv()

app = Flask(__name__)

# ── Gemini config ─────────────────────────────────────────────────────────────
# Free tier: 1500 requests/day, no credit card needed.
# Get a key at https://aistudio.google.com/app/apikey
# Add your key to a .env file: GEMINI_API_KEY=your_key_here
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    'gemini-2.5-flash:generateContent'
)

NOVA16_SYSTEM_PROMPT = """You are an expert assembly programmer for the NOVA-16 ISA emulator.

NOVA-16 is a custom 16-bit RISC architecture with:
- 16 general-purpose registers: R0-R15
- 256-word memory (address 0-255)
- Hardware stack (SP starts at 255, grows downward)
- 4 flags: Zero(Z), Negative(N), Carry(C), Overflow(V)

INSTRUCTION SET (you may ONLY use these):
  LOADI Rd, #imm       -- Rd = imm  (imm range: -1024..1023)
  LOAD  Rd, #addr      -- Rd = mem[addr]
  STORE Rs, #addr      -- mem[addr] = Rs
  ADD   Rd, Rs1, Rs2   -- Rd = Rs1 + Rs2
  ADDI  Rd, Rs, #imm   -- Rd = Rs + imm  (imm range: -64..63)
  SUB   Rd, Rs1, Rs2   -- Rd = Rs1 - Rs2
  SUBI  Rd, Rs, #imm   -- Rd = Rs - imm  (imm range: -64..63)
  MUL   Rd, Rs1, Rs2   -- Rd = Rs1 x Rs2
  AND   Rd, Rs1, Rs2   -- Rd = Rs1 & Rs2
  OR    Rd, Rs1, Rs2   -- Rd = Rs1 | Rs2
  XOR   Rd, Rs1, Rs2   -- Rd = Rs1 ^ Rs2
  NOT   Rd, Rs         -- Rd = ~Rs
  SHL   Rd, Rs, #n     -- Rd = Rs << n  (n: 0..15)
  SHR   Rd, Rs, #n     -- Rd = Rs >> n  (n: 0..15)
  JUMP  #addr          -- PC = addr (or label)
  JZ    #addr          -- jump if Z=1
  JNZ   #addr          -- jump if Z=0
  JLT   #addr          -- jump if N=1
  JGT   #addr          -- jump if N=0 and Z=0
  PUSH  Rs             -- push Rs onto stack
  POP   Rd             -- pop top of stack into Rd
  CALL  #addr          -- push PC, jump to addr
  RET                  -- pop and jump
  HALT                 -- stop execution

SYNTAX RULES:
- Labels: LABEL: on its own line, then reference with JUMP LABEL or JNZ LABEL
- Immediates: decimal (42), hex (0xFF), binary (0b1010)
- Comments start with ;
- ADDI/SUBI immediate limited to -64..63; use LOADI+ADD for bigger values

OUTPUT FORMAT — CRITICAL:
- Return ONLY raw assembly code, absolutely nothing else
- NO markdown, NO backticks, NO fences like ```
- NO explanations before or after the code
- Add brief ; comments inside the code
- Every program must end with HALT"""


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run_program():
    source = request.json.get('source', '')
    try:
        words = assemble(source)
        cpu = CPU()
        cpu.load_program(words)
        cpu.run(trace=False)
        return jsonify({
            'success':   True,
            'registers': list(cpu.regs),
            'memory':    list(cpu.memory[:64]),
            'pc':        cpu.pc,
            'sp':        cpu.sp,
            'flags':     {'Z': cpu.Z, 'N': cpu.N, 'C': cpu.C, 'V': cpu.V},
            'cycles':    cpu.total_cycles,
            'cpi':       round(cpu.total_cycles / cpu.instructions, 3) if cpu.instructions else 0,
            'cache':     {'hits': cpu.cache.hits, 'misses': cpu.cache.misses},
            'hazards':   {'stalls': cpu.hz.stalls, 'forwards': cpu.hz.forwards},
            'bp':        {'accuracy': round(cpu.bp.accuracy, 1)},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/ai', methods=['POST'])
def ai_generate():
    """Generate NOVA-16 assembly using Google Gemini API."""
    data        = request.json or {}
    user_prompt = data.get('prompt', '').strip()

    if not user_prompt:
        return jsonify({'success': False, 'error': 'No prompt provided.'})
    if not GEMINI_API_KEY:
        return jsonify({'success': False, 'error': 'Gemini API key not configured. Add GEMINI_API_KEY to your .env file.'})

    url     = GEMINI_URL + '?key=' + GEMINI_API_KEY
    payload = json.dumps({
        'system_instruction': {'parts': [{'text': NOVA16_SYSTEM_PROMPT}]},
        'contents': [{'parts': [{'text': user_prompt}]}],
        'generationConfig': {
            'temperature':     0.2,   # low = more deterministic / correct code
            'maxOutputTokens': 1024,
        },
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))

        # Extract text from Gemini response structure
        code = (
            result
            .get('candidates', [{}])[0]
            .get('content', {})
            .get('parts', [{}])[0]
            .get('text', '')
            .strip()
        )

        if not code:
            return jsonify({'success': False, 'error': 'Gemini returned an empty response.'})

        # Strip markdown fences if the model added them anyway
        if '```' in code:
            lines = [l for l in code.split('\n') if not l.strip().startswith('```')]
            code  = '\n'.join(lines).strip()

        return jsonify({'success': True, 'code': code})

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            msg = json.loads(body).get('error', {}).get('message', body)
        except Exception:
            msg = body
        return jsonify({'success': False, 'error': f'Gemini API error: {msg}'})

    except urllib.error.URLError as e:
        return jsonify({'success': False, 'error': f'Network error: {e.reason}'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True)