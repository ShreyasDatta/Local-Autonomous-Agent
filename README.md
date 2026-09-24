<div align="center">

# 🤖 Local-First Autonomous Agent

**A smart, fully private AI agent that writes code, runs commands, and manages tasks entirely on your own hardware.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-black.svg)](https://ollama.ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

</div>

> **No API keys. No cloud servers. No data leaks.** This project is a completely air-gapped agentic assistant that runs locally via Ollama. It was built to prove that you don't need heavy frameworks or expensive cloud models to build a highly capable, autonomous AI.

### Hi👋 
This repository is designed to be accessible, transparent, and easy to run on standard consumer hardware (like a 16GB VRAM GPU). 

While this system is completely **model-agnostic** (meaning you can easily swap in Llama 3.1, Gemma, or Mistral), it defaults to `qwen2.5-coder:14b-instruct`. We use Qwen because it punches incredibly far above its weight class when writing code and following strict instructions locally.

---

## 📖 The Deep-Dive Architecture Report
For advanced developers wanting to look under the hood at the hardcore engineering—including our Key-Value (KV) cache retention strategies, VRAM allocation math, and 40-case execution logs—please read our detailed [*Why Local AI Agents Secretly Fail**](https://media.istockphoto.com/id/2171020551/vector/coming-soon-speechbubble-advertising-with-megaphone-icon.jpg?s=2048x2048&w=is&k=20&c=G1qMTFcbJoXIYT16KZjx7ElyGtilayAfy-JHSBIXixk=](https://shreyas-systems.hashnode.dev/debugging-local-llm-agents)).

---

## ✨ How It Works (The Architecture)

### 🛡️ 1. Smart Tool Routing (The Gatekeeper Pattern)
Smaller local models often suffer from "tool magnetism"—they get confused and try to trigger tools (like writing files or doing math) even when you just want to have a casual chat. 

To fix this, we built a **Guard-Gated Two-Phase Decoupled Dispatch** pipeline. In plain English: the system acts as a strict gatekeeper. It forces the AI to chat naturally by default, and only hands the AI its tools when the system explicitly detects that a tool is needed. This eliminates errors and makes the AI significantly faster.

### ⚡ 2. No Bloated Frameworks
We deliberately avoided heavy, complicated AI frameworks (like LangChain or AutoGen) that eat up memory and hide how the AI actually works. This project is built using:
* **Pure Python** standard libraries for total transparency.
* **Strict Pydantic** data contracts to ensure the AI doesn't hallucinate fake data.
* **Direct REST calls** to Ollama for maximum speed.

### 🖥️ 3. Two Ways to Interact
* **Interactive Terminal (CLI):** A lightning-fast interface for developers, featuring safety "circuit breakers" that ask for your permission before the AI modifies any of your files.
* **Browser Chat (GUI):** A clean, lightweight web interface for a rich, visual chatting experience.

---

## 📂 Repository Structure

```text
├── agent.py                 # Main entry point for CLI and GUI runners
├── core/                    # The raw-Python engine, intent router, and tool registry
├── personalities/           # AI system prompts and configurations
├── regression_suite.py      # Automated testing script to verify AI behavior
├── tests/                   # Additional isolated unit tests
├── requirements.txt         # Minimal dependency manifest
└── .gitignore               # Excludes virtual environments, models, and local databases
```

## 🚀 Quick Start & Installation

### Prerequisites

Before getting started, ensure the following requirements are met:

- **OS:** Windows 10/11 (PowerShell recommended), macOS, or Linux
- **Python:** 3.10 or higher
- **Inference Backend:** [Ollama](https://ollama.ai/) installed and running locally at `http://localhost:11434`

### 1. Environment Setup

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/ShreyasDatta/Local-Autonomous-Agent.git
cd Local-Autonomous-Agent

python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Model Acquisition

Pull the benchmark models using the Ollama CLI:

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
ollama pull nomic-embed-text:latest
```

> 💡 **Note:** If you are running on lower-VRAM hardware, you can easily swap these models for smaller 7B/8B variants through the configuration files.

### 3. Run the Agent

#### Interactive CLI Mode

Launch the terminal-based interface:

```bash
python agent.py --cli
```

#### Browser GUI Mode

Launch the lightweight web interface:

```bash
python agent.py --gui --port 8080
```

Once started, open:

```text
http://127.0.0.1:8080
```

in your browser.

---

## 🧪 Automated Testing

This repository includes a comprehensive **Regression Suite** designed to validate:

- Multi-turn conversational flow (Does it remember what you said?)
- Fast-path regex guards (Does it do math instantly?)
- Tool-routing correctness (Does it use tools only when asked?)

Run the local test harness with:

```bash
python regression_suite.py
```

---

## 📚 References

This project draws inspiration from the following resources:

1. **https://www.anthropic.com/engineering/building-effective-agents**  
   Insights into practical agentic design patterns and production-ready orchestration strategies from Anthropic.

2. **https://github.com/ashishpatel26/500-AI-Agents-Projects**  
   A large open-source catalog showcasing diverse AI agent implementations and architectures.

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
