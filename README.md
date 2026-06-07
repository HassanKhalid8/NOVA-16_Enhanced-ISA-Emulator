# NOVA-16_Enhanced-ISA-Emulator

A browser-based emulator for **NOVA-16** — a custom 16-bit RISC architecture — built with Python (Flask) and vanilla JavaScript. Write, assemble, and execute NOVA-16 assembly in real time, with a full pipeline visualizer, cache simulator, hazard detector, and an AI code generator powered by Google Gemini.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python) ![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask) ![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Live assembler & emulator** — write assembly in the editor and run or step through it instruction by instruction
- **Pipeline visualizer** — see the IF → ID → EX → MEM → WB stages animate in real time
- **L1 direct-mapped cache** — 8-line write-through cache with hit/miss tracking and visual feedback
- **RAW hazard detection** — data hazards are detected, stalls inserted, and forwarding paths shown automatically
- **2-bit saturating branch predictor** — tracks prediction accuracy across the program
- **CPI breakdown** — cycles split into ALU / MEM / Branch / Stall categories with live bar chart
- **Register & memory viewer** — all 16 registers and 256 memory words displayed and highlighted on change
- **AI code generator** — describe what you want in plain English and Gemini generates valid NOVA-16 assembly
- **Example programs** — factorial, Fibonacci, GCD, bubble sort, CALL/RET demo and more built in

---

## NOVA-16 Architecture

| Feature | Detail |
|---|---|
| Word size | 16-bit |
| Instruction word | 20-bit |
| Registers | 16 general-purpose (R0–R15) |
| Memory | 256 words |
| Stack | Hardware stack, SP starts at 255, grows downward |
| Flags | Zero (Z), Negative (N), Carry (C), Overflow (V) |
| Instructions | 24 total — ALU, memory, branches, CALL/RET, PUSH/POP |

---

## Installation

**1. Clone the repo:**
```bash
git clone https://github.com/your-username/nova16-emulator.git
cd nova16-emulator
```

**2. Install dependencies:**
```bash
pip install flask python-dotenv
```

**3. Add your Gemini API key:**

Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_key_here
```
Get a free key (no credit card needed) at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) — 1000 free requests/day.

**4. Run the app:**
```bash
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Project Structure

```
nova16-emulator/
├── app.py                  # Flask backend — runs assembler, emulator, Gemini API
├── nova16_emulator.py      # NOVA-16 CPU core — cache, hazards, branch predictor
├── requirements.txt
├── .env                    # Your Gemini API key (never committed to Git)
├── .gitignore
└── templates/
    └── index.html          # Full frontend — editor, visualizer, panels
```

---

## Instruction Set

```
LOADI Rd, #imm       Rd = imm  (-1024 to 1023)
LOAD  Rd, #addr      Rd = mem[addr]
STORE Rs, #addr      mem[addr] = Rs
ADD   Rd, Rs1, Rs2   Rd = Rs1 + Rs2
ADDI  Rd, Rs, #imm   Rd = Rs + imm  (-64 to 63)
SUB   Rd, Rs1, Rs2   Rd = Rs1 - Rs2
SUBI  Rd, Rs, #imm   Rd = Rs - imm  (-64 to 63)
MUL   Rd, Rs1, Rs2   Rd = Rs1 × Rs2
AND / OR / XOR       Bitwise operations
NOT   Rd, Rs         Rd = ~Rs
SHL / SHR            Shift left / right by n bits
JUMP / JZ / JNZ      Unconditional and conditional jumps
JLT / JGT            Jump if less than / greater than
PUSH / POP           Stack operations
CALL / RET           Subroutine call and return
HALT                 Stop execution
```

Labels, hex literals (`0xFF`), binary literals (`0b1010`), and `;` comments are all supported.

---

## AI Code Generator

The built-in AI panel lets you describe a program in plain English and generates valid NOVA-16 assembly automatically. It uses **Google Gemini 2.5 Flash Lite** with automatic retry on busy errors.

Examples you can try:
- *"Compute factorial of 5 and store in mem[0]"*
- *"Sort three values in R0, R1, R2 in ascending order"*
- *"Compute GCD of two numbers using Euclid's algorithm"*
- *"Demonstrate a subroutine using CALL and RET"*

---

## License

MIT
