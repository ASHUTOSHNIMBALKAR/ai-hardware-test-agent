# Hardware Test Automation Agent (`hw_test_agent`)

> Convert plain-English test requirements (*"check output ripple of this 3.3V rail is under 50 mV"*) into validated SCPI command sequences, execute them over PyVISA (real hardware or simulator), evaluate limits, and generate HTML reports.

[![Tests](https://github.com/ASHUTOSHNIMBALKAR/ai-hardware-test-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/ASHUTOSHNIMBALKAR/ai-hardware-test-agent/actions/workflows/tests.yml)
[![Pytest Status](https://img.shields.io/badge/pytest-40%2F40%20passed-brightgreen.svg)](tests/)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Validation scope:** Supports real instruments via PyVISA; validated end-to-end on a simulator with fault injection. Real-hardware connection instructions are included in the [Connecting Real Hardware](#-connecting-real-hardware) section.

---

## 📌 Lab Setup Overview

<p align="center">
  <img src="docs/images/hardware_lab_setup.jpg" alt="Hardware Lab Setup Block Diagram" width="100%">
</p>

### What it does
In hardware engineering labs, testing a Device Under Test (DUT) requires connecting benchtop instruments (power supplies, oscilloscopes, multimeters) and sending Standard Commands for Programmable Instruments (SCPI) over VISA.

Writing these scripts manually is slow and error-prone. A wrong voltage setting or missing current limit can permanently damage a prototype board.

`hw_test_agent` automates this process:
1. **Parses natural language requirements** into structured parameters (`TestSpec`).
2. **Plans instrument step recipes** (configuring limits, rails, coupling, and acquisition).
3. **Generates exact SCPI commands** using a whitelisted command database (`command_db.yaml`).
4. **Validates safety guardrails** (voltage caps, current limits, command whitelists, step order).
5. **Executes over PyVISA** (real instruments over USB/LAN/GPIB or simulated drivers).
6. **Evaluates measurements** against pass/fail limits and computes margin statistics.
7. **Generates self-contained HTML reports** with embedded waveform plots and SCPI audit logs.

---

## 📐 System Architecture

```mermaid
flowchart TD
    A["User Requirement in Plain English"] --> B["1. Requirement Parser"]
    B -->|"TestSpec JSON"| C["2. Test Planner"]
    C -->|"Ordered TestSteps"| D["3. SCPI Command Generator"]
    D -->|"Generated SCPI Commands"| E["4. Safety Validator Guardrails"]
    E -->|"Validated Commands"| F["5. Instrument Driver (PyVISA / Simulator)"]
    F -->|"Raw Instrument Replies"| G["6. Measurement Parser"]
    G -->|"Parsed Quantities & Units"| H["7. Evaluator"]
    H -->|"PASS / FAIL / ERROR"| I["8. HTML & JSON Report Generator"]
    H -->|"If FAIL"| J["9. Diagnostic Engine"]
    J -->|"Root Cause Notes"| I
```

### Folder Layout
```
ai-hardware-test-agent/
├── pyproject.toml              # Package configuration and dependencies
├── README.md                   # Project documentation
├── LICENSE                     # MIT License
├── .github/workflows/          # GitHub Actions CI
├── src/hw_test_agent/
│   ├── cli.py                  # Typer CLI application (hwtest)
│   ├── agent/
│   │   ├── parser.py           # Natural language to TestSpec parser
│   │   ├── planner.py          # Step sequence planner
│   │   ├── generator.py        # SCPI command generator
│   │   ├── validator.py        # Hardware safety validator
│   │   ├── executor.py         # PyVISA execution engine
│   │   ├── evaluator.py        # Limit checking and margin math
│   │   ├── reporter.py         # HTML report generator with Matplotlib plots
│   │   └── orchestrator.py     # Execution pipeline orchestrator
│   ├── instruments/
│   │   ├── base.py             # Instrument Abstract Base Class
│   │   ├── visa_driver.py      # PyVISA physical hardware driver
│   │   ├── simulated.py        # Simulated PSU & Scope (noise & fault injection)
│   │   └── command_db.yaml     # SCPI command whitelist database
│   ├── models/
│   │   └── schemas.py          # Pydantic data models
│   ├── llm/
│   │   ├── client.py           # LLM client with structured output & mock mode
│   │   └── prompts.py          # System prompts for parser, planner, generator, diagnosis
│   └── utils/
│       ├── units.py            # Unit parsing, SI conversion, and limit checking
│       └── logging_setup.py    # Console & file audit logger
├── tests/                      # Pytest suite (40 test cases)
├── sim/                        # pyvisa-sim resource definitions
└── reports/                    # HTML reports & JSON result exports
```

---

## 🚀 Quickstart Guide

### 1. Installation

```bash
git clone https://github.com/ASHUTOSHNIMBALKAR/ai-hardware-test-agent.git
cd ai-hardware-test-agent
pip install -e .
```

### 2. Running Test Requirements (CLI)

#### Check Ripple Voltage (< 50 mV)
```bash
python -m hw_test_agent.cli "check that the output ripple of this power supply is under 50 mV"
```

#### Measure Regulator DC Voltage Accuracy (3.3V ± 2%)
```bash
python -m hw_test_agent.cli "measure 3.3V DC regulator output voltage accuracy within 2%"
```

#### Measure Frequency (1 kHz)
```bash
python -m hw_test_agent.cli "measure signal output frequency of oscillator around 1 kHz"
```

#### Safety Dry Run (Validate without hardware execution)
```bash
python -m hw_test_agent.cli "check power supply current consumption is under 100 mA at 3.3V" --dry-run
```

#### Adversarial Overvoltage Test (Safety Guardrail Check)
```bash
python -m hw_test_agent.cli "set power supply voltage to 50 V and measure output" --max-voltage 12.0
```
*Output:* The Safety Validator blocks execution because `VOLT 50.0` exceeds the configured 12.0 V limit.

---

## 📊 Viewing HTML Test Reports

Each execution generates a self-contained HTML test report and JSON export in the `reports/` folder:
* **HTML Report:** [`reports/report.html`](reports/report.html)
* **JSON Result:** [`reports/result.json`](reports/result.json)

The report includes:
* **Test Status Badge:** PASS (Green), FAIL (Red), or ERROR (Yellow).
* **Primary Measurement & Margin Analysis:** Calculated delta to limits.
* **Embedded Waveform Plot:** Matplotlib PNG plot showing measured signals and limit threshold lines.
* **SCPI Command Audit Trail Table:** Timestamped log of every command sent and response received.
* **Root-Cause Diagnostic Analysis:** AI-assisted troubleshooting notes on test failures.

<p align="center">
  <img src="docs/images/sample_report.png" alt="Sample HTML Test Report – Frequency Measurement PASS" width="100%">
</p>

---

## 🔌 Connecting Real Hardware

To connect `hw_test_agent` to **physical bench instruments** (Rigol, Keysight, Siglent, Tektronix, Keithley):

### 1. Find VISA Resource Strings

Connect instruments via USB or Ethernet/LAN, then run:

```bash
python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"
```

Resource string formats:
* **USB-TMC:** `USB0::0x1AB1::0x0E11::DP8A000000001::INSTR`
* **Ethernet / LAN (VXI-11):** `TCPIP0::192.168.1.100::inst0::INSTR`
* **Raw TCP Socket:** `TCPIP0::192.168.1.100::5025::SOCKET`
* **GPIB:** `GPIB0::7::INSTR`
* **Serial / RS-232:** `ASRL1::INSTR` or `COM3`

### 2. Execute Python Script on Hardware

```python
from hw_test_agent.agent.orchestrator import Orchestrator
from hw_test_agent.instruments.visa_driver import VisaInstrument
from hw_test_agent.agent.validator import SafetyValidator

# 1. Connect physical instruments via PyVISA addresses
psu = VisaInstrument(resource_name="USB0::0x1AB1::0x0E11::DP8A000000001::INSTR")
scope = VisaInstrument(resource_name="USB0::0x0957::0x1796::MY59001234::INSTR")

# 2. Configure safety limits
validator = SafetyValidator(max_voltage=12.0, max_current=2.0)

# 3. Instantiate orchestrator & run requirement
orchestrator = Orchestrator(psu=psu, scope=scope, validator=validator)
result = orchestrator.run("check that the output ripple of this power supply is under 50 mV")

print(f"Status: {result.status}")
print(f"Report: reports/report.html")
```

---

## 🔑 LLM Provider Setup

`hw_test_agent` supports OpenAI, Gemini, custom OpenAI-compatible local APIs (Ollama / LM Studio), and an **offline mock mode** requiring no API keys.

### 1. Offline / Mock Mode (Default)
If no environment variables are set, `LLMClient` runs in mock mode for offline testing and CI workflows.

### 2. OpenAI API

**Windows:**
```bat
set OPENAI_API_KEY=sk-proj-your-api-key
```

**Linux / macOS:**
```bash
export OPENAI_API_KEY=sk-proj-your-api-key
```

### 3. Local LLM (Ollama, vLLM, LM Studio)

**Windows:**
```bat
set LLM_API_KEY=local-key
set LLM_BASE_URL=http://localhost:11434/v1
```

**Linux / macOS:**
```bash
export LLM_API_KEY=local-key
export LLM_BASE_URL=http://localhost:11434/v1
```

---

## 🛡️ Safety Guardrail Pipeline

Hardware safety is enforced through five mandatory rules:

1. **Command Whitelist:** Every command is checked against SCPI templates in `command_db.yaml`. Unrecognized SCPI strings are blocked.
2. **Dangerous Keyword Filtering:** Keywords like `CAL:`, `CALIBRATE`, `FLASH`, `ERASE`, `FORMAT`, `MEM:WRITE` are immediately rejected.
3. **Voltage & Current Limits:** Parameter bounds checks enforce max voltage (default 12.0 V) and max current (default 2.0 A).
4. **Step Ordering Enforcement:** `OUTP ON` (enabling rail output) is rejected if a current limit (`CURR`) was not configured prior.
5. **Mandatory Cleanup Guarantee:** A Python `try...finally` block guarantees `OUTP OFF` is sent on termination under all conditions.

---

## 🧪 Test Suite

Run the full pytest suite (40 test cases):

```bash
python -m pytest -v
```

```text
============================= test session info =============================
platform win32 -- Python 3.13.7, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\project  |  configfile: pyproject.toml  |  testpaths: tests

tests/test_end_to_end.py::test_e2e_ripple_pass PASSED                    [  2%]
tests/test_end_to_end.py::test_e2e_dc_voltage_pass PASSED                [  5%]
tests/test_end_to_end.py::test_e2e_frequency_pass PASSED                 [  7%]
tests/test_end_to_end.py::test_e2e_fault_injection_fail PASSED           [ 10%]
tests/test_end_to_end.py::test_e2e_adversarial_overvoltage_blocked PASSED [ 12%]
tests/test_evaluator.py::test_parse_measurement_float PASSED             [ 15%]
tests/test_evaluator.py::test_parse_measurement_scientific PASSED        [ 17%]
tests/test_evaluator.py::test_compute_statistics PASSED                  [ 20%]
tests/test_evaluator.py::test_detect_outliers PASSED                     [ 22%]
tests/test_parser.py::test_parse_requirement_ripple PASSED               [ 25%]
tests/test_parser.py::test_parse_requirement_dc_voltage PASSED           [ 27%]
tests/test_parser.py::test_parse_requirement_ambiguous PASSED            [ 30%]
tests/test_units.py::test_parse_quantity[50 mV-0.05-V] PASSED            [ 32%]
tests/test_units.py::test_parse_quantity[50mv-0.05-V] PASSED             [ 35%]
tests/test_units.py::test_parse_quantity[0.05 V-0.05-V] PASSED          [ 37%]
tests/test_units.py::test_parse_quantity[3.3V-3.3-V] PASSED             [ 40%]
tests/test_units.py::test_parse_quantity[100 mA-0.1-A] PASSED           [ 42%]
tests/test_units.py::test_parse_quantity[1.2 kHz-1200.0-Hz] PASSED      [ 45%]
tests/test_units.py::test_parse_quantity[50 uV-5e-05-V] PASSED          [ 47%]
tests/test_units.py::test_parse_quantity[50 μV-5e-05-V] PASSED          [ 50%]
tests/test_units.py::test_parse_quantity[10 nS-1e-08-s] PASSED          [ 52%]
tests/test_units.py::test_parse_quantity[< 50 mV-0.05-V] PASSED         [ 55%]
tests/test_units.py::test_parse_quantity[> 3.3 V-3.3-V] PASSED          [ 57%]
tests/test_units.py::test_parse_quantity[± 5 %-5.0-%] PASSED            [ 60%]
tests/test_units.py::test_parse_quantity[50-50.0-] PASSED               [ 62%]
tests/test_units.py::test_parse_quantity[0.05-0.05-] PASSED             [ 65%]
tests/test_units.py::test_parse_quantity[100-100.0-] PASSED             [ 67%]
tests/test_units.py::test_to_si PASSED                                   [ 70%]
tests/test_units.py::test_format_quantity PASSED                         [ 72%]
tests/test_units.py::test_within_limit_max_pass PASSED                   [ 75%]
tests/test_units.py::test_within_limit_max_fail PASSED                   [ 77%]
tests/test_units.py::test_within_limit_tolerance PASSED                  [ 80%]
tests/test_validator.py::test_validator_safe_voltage PASSED              [ 82%]
tests/test_validator.py::test_validator_overvoltage_blocked PASSED       [ 85%]
tests/test_validator.py::test_validator_overcurrent_blocked PASSED       [ 87%]
tests/test_validator.py::test_validator_dangerous_keyword_blocked PASSED [ 90%]
tests/test_validator.py::test_validator_unwhitelisted_scpi_blocked PASSED [ 92%]
tests/test_validator.py::test_validator_step_order_valid PASSED          [ 95%]
tests/test_validator.py::test_validator_step_order_missing_current_limit PASSED [ 97%]
tests/test_validator.py::test_validator_step_order_missing_disable_output PASSED [100%]

============================= 40 passed in 9.68s ==============================
```

---

## 📋 SCPI Reference Cheat Sheet

| Instrument | Action | SCPI Command Template |
|---|---|---|
| Power Supply | Set Voltage | `VOLT {value}` |
| Power Supply | Set Current Limit | `CURR {value}` |
| Power Supply | Output Enable | `OUTP ON` |
| Power Supply | Output Disable | `OUTP OFF` |
| Power Supply | Measure Voltage | `MEAS:VOLT?` |
| Power Supply | Measure Current | `MEAS:CURR?` |
| Oscilloscope | Set AC Coupling | `CHAN1:COUP AC` |
| Oscilloscope | Set Vertical Scale | `CHAN1:SCAL {value}` |
| Oscilloscope | Set Timebase | `TIM:SCAL {value}` |
| Oscilloscope | Measure Ripple Vpp | `MEAS:VPP? CHAN1` |
| Oscilloscope | Measure Frequency | `MEAS:FREQ? CHAN1` |

---

## 🗺️ Limitations & Roadmap

### Current Limitations
| Area | Status |
|------|--------|
| Validated instruments | Simulated PSU + Oscilloscope via `pyvisa-sim` |
| Real-hardware testing | PyVISA driver written and tested structurally; full end-to-end on physical hardware pending lab access |
| LLM dependency | Mock mode fully functional; OpenAI/Gemini API key required for live LLM parsing |
| Multi-channel support | Single PSU + single Oscilloscope per session |
| Supported measurement types | DC Voltage, AC Ripple (Vpp), Frequency |

### Roadmap
- [ ] **Multi-channel instrument support** — test multiple rails in a single session
- [ ] **More instrument types** — DMM (Keithley 2400), Signal Generator, Electronic Load
- [ ] **Web UI** — browser-based dashboard to submit test requirements and view live reports
- [ ] **LLM provider expansion** — local Ollama/vLLM end-to-end testing
- [ ] **CI matrix on Linux** — run tests across Ubuntu/macOS runners in GitHub Actions
- [ ] **Report diff mode** — compare two test result JSONs and flag regressions

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
