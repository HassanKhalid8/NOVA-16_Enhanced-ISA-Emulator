<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:D9C9BA,45:A28973,100:6E4F32&height=190&section=header&text=NOVA-16&fontColor=2E2117&fontSize=72&fontAlign=50&fontAlignY=34&desc=Enhanced%20ISA%20Emulator&descSize=20&descAlign=50&descAlignY=56&animation=fadeIn" width="100%" alt="NOVA-16" />

<img src="https://readme-typing-svg.demolab.com?font=IBM+Plex+Mono&weight=600&size=22&pause=1200&color=6E4F32&center=true&vCenter=true&width=780&height=55&lines=A+16-bit+RISC+architecture+in+your+browser;5-stage+pipeline+with+hazard+detection;L1+cache+%2B+2-bit+branch+predictor;Write+assembly.+Watch+it+execute." alt="typing tagline" />

<br/>

![Python](https://img.shields.io/badge/Python-3.10%2B-8C6E52?style=flat-square&logo=python&logoColor=F8F4EE&labelColor=2E2117)
![Flask](https://img.shields.io/badge/Flask-3.0-A28973?style=flat-square&logo=flask&logoColor=F8F4EE&labelColor=2E2117)
![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-6D3A6B?style=flat-square&logo=googlegemini&logoColor=F8F4EE&labelColor=2E2117)
![Vanilla JS](https://img.shields.io/badge/Vanilla-JS-7A4E0C?style=flat-square&logo=javascript&logoColor=F8F4EE&labelColor=2E2117)
![License](https://img.shields.io/badge/License-MIT-3D6B33?style=flat-square&labelColor=2E2117)

</div>

---

**NOVA-16** is a custom 16-bit RISC architecture and a browser-based emulator for it, built with Flask and vanilla JavaScript. Write assembly in the editor, then run it or step through it one instruction at a time and watch the pipeline, cache, hazard unit, and branch predictor react in real time.

<!-- Drop a screenshot in here once you have one:
<div align="center"><img src="assets/screenshot.png" width="900" alt="NOVA-16 emulator interface" /></div>
-->

## The pipeline

Every instruction walks the five classic stages. Forwarding paths and stall insertion are detected automatically and drawn as they happen.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'IBM Plex Mono, monospace','primaryColor':'#eae0d4','primaryTextColor':'#2e2117','primaryBorderColor':'#8c6e52','lineColor':'#a28973','tertiaryColor':'#f8f4ee'}}}%%
flowchart LR
    IF["IF<br/>fetch"] --> ID["ID<br/>decode"] --> EX["EX<br/>execute"] --> MEM["MEM<br/>access"] --> WB["WB<br/>writeback"]
    EX  -. "forward" .-> ID
    MEM -. "forward" .-> ID
    MEM -. "load-use: insert stall" .-> IF

    style IF  fill:#e6edf2,stroke:#2f5d78,color:#2f5d78,stroke-width:2px
    style ID  fill:#f0e8ef,stroke:#6d3a6b,color:#6d3a6b,stroke-width:2px
    style EX  fill:#e8efe6,stroke:#3d6b33,color:#3d6b33,stroke-width:2px
    style MEM fill:#f4ecdd,stroke:#7a4e0c,color:#7a4e0c,stroke-width:2px
    style WB  fill:#e4efee,stroke:#1f6b66,color:#1f6b66,stroke-width:2px
```

## Features

| | |
|---|---|
| **Live assembler & emulator** | Assemble from the editor, then `run` continuously or `step` instruction by instruction at an adjustable speed |
| **Pipeline visualizer** | IF → ID → EX → MEM → WB, each stage showing its current instruction, decoded fields, and raw 20-bit word |
| **L1 data cache** | 8-line direct-mapped, write-through, with per-line tag/value display and hit/miss flashes |
| **RAW hazard detection** | Load-use hazards insert a stall; everything else forwards, and both are reported live |
| **2-bit saturating predictor** | Branch predictions tracked with the counter state (SN/WN/WT/ST) drawn as it saturates |
| **CPI breakdown** | Cycles split into ALU / MEM / Branch / Stall with a live bar chart |
| **Register & memory viewer** | All 16 registers plus 256 memory words, colour-coded for code, stored data, stack, and the current PC |
| **Execution trace** | Every retired instruction with its address, raw encoding, effect, and any hazard tag |
| **AI code generator** | Describe a computation in English and Gemini writes the NOVA-16 assembly — cancellable mid-request |

## Architecture

| Feature | Detail |
|---|---|
| Word size | 16-bit |
| Instruction word | 20-bit |
| Registers | 16 general-purpose (`R0`–`R15`) |
| Memory | 256 words |
| Stack | Hardware stack, `SP` starts at 255 and grows downward |
| Flags | Zero `Z`, Negative `N`, Carry `C`, Overflow `V` |
| Instructions | 24 — ALU, memory, branches, `CALL`/`RET`, `PUSH`/`POP` |
| Cycle costs | ALU 1 · MEM 2 · MUL 3 · Branch 3 · +1 per stall |

**Instruction encoding** — five layouts share the 20-bit word:

```
Register    op(5) | dst(4) | src1(4) | src2(4) | 000
Immediate   op(5) | dst(4) | imm(11 signed)
Reg + imm   op(5) | dst(4) | src1(4) | imm(7 signed)
Store       op(5) | src(4) | addr(8 unsigned)
Jump / Call op(5) | addr(8 unsigned)
```

## Cache lookup

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'IBM Plex Mono, monospace','primaryColor':'#eae0d4','primaryTextColor':'#2e2117','primaryBorderColor':'#8c6e52','lineColor':'#a28973','tertiaryColor':'#f8f4ee'}}}%%
flowchart LR
    A["LOAD / STORE addr"] --> B["index = addr mod 8<br/>tag = addr div 8"]
    B -->|"valid line, tag matches"| H["HIT"]
    B -->|"otherwise"| M["MISS"]
    M --> R["refill line from<br/>256-word memory"]

    style A fill:#eae0d4,stroke:#8c6e52,color:#2e2117
    style B fill:#f8f4ee,stroke:#a28973,color:#2e2117
    style H fill:#e8efe6,stroke:#3d6b33,color:#3d6b33,stroke-width:2px
    style M fill:#f4e7e4,stroke:#8f2b1e,color:#8f2b1e,stroke-width:2px
    style R fill:#f4ecdd,stroke:#7a4e0c,color:#7a4e0c
```

## Quick start

**1. Clone and enter the repo**

```bash
git clone https://github.com/HassanKhalid8/NOVA-16_Enhanced-ISA-Emulator.git
cd NOVA-16_Enhanced-ISA-Emulator
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Add your Gemini API key** (optional — only the AI panel needs it)

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
```

Free keys, no credit card, at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

**4. Run**

```bash
python app.py
```

Then open **http://127.0.0.1:5000**.

## Instruction set

| Instruction | Effect |
|---|---|
| `LOADI Rd, imm` | `Rd = imm` (−1024…1023) |
| `LOAD Rd, addr` | `Rd = mem[addr]` |
| `STORE Rs, addr` | `mem[addr] = Rs` |
| `ADD Rd, Rs1, Rs2` | `Rd = Rs1 + Rs2` |
| `ADDI Rd, Rs, imm` | `Rd = Rs + imm` (−64…63) |
| `SUB Rd, Rs1, Rs2` | `Rd = Rs1 − Rs2` |
| `SUBI Rd, Rs, imm` | `Rd = Rs − imm` (−64…63) |
| `MUL Rd, Rs1, Rs2` | `Rd = Rs1 × Rs2` |
| `AND` `OR` `XOR` | Bitwise, `Rd = Rs1 ⊕ Rs2` |
| `NOT Rd, Rs` | `Rd = ~Rs` |
| `SHL` `SHR` | `Rd = Rs << n` / `Rs >> n` (n = 0…15) |
| `JUMP addr` | `PC = addr` |
| `JZ` `JNZ` | Jump if `Z` set / clear |
| `JLT` `JGT` | Jump if negative / if positive and non-zero |
| `PUSH Rs` `POP Rd` | Stack push / pop |
| `CALL addr` `RET` | Subroutine call and return |
| `HALT` | Stop execution |

Labels (`LOOP:` … `JUMP LOOP`), hex (`0xFF`), binary (`0b1010`), and `;` comments are all supported.

**Built-in examples:** add numbers · countdown loop · Fibonacci · bubble sort · `CALL`/`RET` · data-hazard demo · bitwise ops.

## AI code generator

Describe a computation and Gemini 2.5 Flash writes the assembly for it:

> *"Compute factorial of 5 and store in mem[0]"*
> *"Sort three values in R0, R1, R2 in ascending order"*
> *"Compute GCD of two numbers using Euclid's algorithm"*

- **Assembly only.** The generator is scoped to NOVA-16 programs — off-topic requests (poems, trivia, other languages) are refused rather than answered, and the server validates that every returned line is a real instruction, label, or comment before it can reach the editor.
- **Cancellable.** A `stop` button appears while a request is in flight; <kbd>Esc</kbd> in the prompt does the same.
- **Ctrl+Enter** generates, and `insert into editor` drops the result straight into the assembler.

## Interface

| Panel | Contents |
|---|---|
| **Left** | Assembly editor, example picker, assemble/step/run/reset controls, speed slider, AI generator |
| **Centre** | 5-stage pipeline, hazard strip, registers, L1 cache, 256-word memory map, execution trace |
| **Right** | CPU state and flags, CPI breakdown, branch predictor, full instruction reference |

## Theme

The interface uses a warm, high-contrast **Rich Brown** palette — every text/background pair meets WCAG AA.

| Swatch | Hex | Role |
|---|---|---|
| ![](https://img.shields.io/badge/-%20-F8F4EE?style=flat-square) | `#f8f4ee` | Page background |
| ![](https://img.shields.io/badge/-%20-D9C9BA?style=flat-square) | `#d9c9ba` | Raised surfaces, hover |
| ![](https://img.shields.io/badge/-%20-BBA591?style=flat-square) | `#bba591` | Borders |
| ![](https://img.shields.io/badge/-%20-A28973?style=flat-square) | `#a28973` | Strong borders, scrollbars |
| ![](https://img.shields.io/badge/-%20-8C6E52?style=flat-square) | `#8c6e52` | Primary accent |
| ![](https://img.shields.io/badge/-%20-6E4F32?style=flat-square) | `#6e4f32` | Buttons, PC marker, headline values |
| ![](https://img.shields.io/badge/-%20-2E2117?style=flat-square) | `#2e2117` | Body text |

Stage and status colours are earthy variants of the same family: IF `#2f5d78` · ID `#6d3a6b` · EX `#3d6b33` · MEM `#7a4e0c` · WB `#1f6b66` · stall `#8f2b1e`.

## Project structure

```
NOVA-16_Enhanced-ISA-Emulator/
├── app.py                  # Flask backend — routes, Gemini bridge, reply validation
├── nova16_emulator.py      # NOVA-16 CPU core — assembler, cache, hazards, predictor
├── templates/
│   └── index.html          # Entire frontend — editor, visualizer, panels, styling
├── requirements.txt
├── .env                    # GEMINI_API_KEY (gitignored)
└── LICENSE
```

## License

MIT — see [LICENSE](LICENSE).

<div align="center">
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6E4F32,55:A28973,100:D9C9BA&height=110&section=footer" width="100%" alt="" />
</div>
