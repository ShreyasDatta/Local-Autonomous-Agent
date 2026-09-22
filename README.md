# **Local Autonomous Agent: Architecture, Setup & Deployment Guide**

# **Overview**

This system runs locally against Ollama using `qwen2.5-coder:14b-instruct-q4_K_M` for both intent probing and task execution. The architecture operates with zero-cloud API dependencies, ensuring that no data leaves the local network.

# **Architecture & Design Highlights**

## **Decoupled Tool Routing (The Gatekeeper Pattern)**

To resolve "tool magnetism"—a common issue in smaller models (like the 8B class) where the model attempts to use tools unnecessarily—this architecture implements the Gatekeeper Pattern. Pure conversational queries are processed in `tools=None` mode by default. Tools are dynamically attached only when the orchestrator detects explicit requirements for mathematical operations or temporal data, ensuring precision and reducing inference latency.

## **Framework-Free Runtime**

The system utilizes Python standard library constructs and direct interaction with native OpenAI-compatible REST endpoints. Model selection and system configuration are managed in `personalities/general_cousin.py`. The runtime uses:

&nbsp;

* `http.server` for the web interface.  
* `urllib` for internal networking.  
* `re` for robust parsing of model outputs.  
* Direct interaction with native OpenAI-compatible REST endpoints.

## **Dual Frontend**

The system provides two distinct ways to interact with the agent:

&nbsp;

1. **Interactive Terminal CLI**: A low-latency interface for developers and system administrators.  
2. **Browser Chat GUI**: A zero-dependency web interface for a rich, visual user experience.

# **Repository Structure & Git Hygiene**

## **Directory Tree**

The repository separates core logic from local runtime artifacts to maintain a clean version control history..

&nbsp;

├── agent.py                 \# Main entry point for CLI and GUI

&nbsp;

├── core/                    \# Logic for tool routing and model orchestration

&nbsp;

├── personalities/           \# System prompts and persona definitions

&nbsp;

├── regression\_suite.py      \# Automated testing script

├── tests/                   \# Golden Regression Suite and unit tests

&nbsp;

├── .gitignore               \# Standard exclusion rules

&nbsp;

├── .venv/                   \# Ignored: Python virtual environment

&nbsp;

├── models/                  \# Ignored: Local GGUF weights

&nbsp;

└── vector\_store/            \# Ignored: SQLite chat history and DB files

## **Git Configuration**

Use the following `.gitignore` to ensure local artifacts are not tracked:\# Python

&nbsp;

.venv/

&nbsp;

\_\_pycache\_\_/

&nbsp;

\*.pyc

&nbsp;

\# Local Assets

&nbsp;

models/

&nbsp;

vector\_store/\*.db

&nbsp;

logs/\*.log

&nbsp;

\# Environment

&nbsp;

.env

# **Prerequisites & Hardware Footprint**

## **System Requirements**

* **OS**: Windows 10/11 (PowerShell recommended), macOS, or Linux.  
* **Python**: 3.10 or higher.  
* **Inference**: Ollama inference server installed and running.

## **Model Asset Footprint**

| Model Asset | Description | Disk Footprint |
| :---- | :---- | :---- |
|  |  |  |
| `qwen2.5-coder:14b-instruct-q4_K_M` | Technical & Coding Tasks | \~9.0 GB |
| `nomic-embed-text:latest` | Vector Embeddings | \~274 MB |

# **Step-by-Step Setup & Installation**

## **1\. Environment Initialization**

Clone the repository and prepare the Python environment:git clone \<repository-url\>

&nbsp;

cd local-autonomous-agent

&nbsp;

python \-m venv .venv

&nbsp;

source .venv/bin/activate  \# On Windows use: .venv\\Scripts\\activate

&nbsp;

pip install pydantic pytest

## **2\. Model Acquisition**

## **3\. Verification**

Confirm the models are correctly indexed:ollama list

# **Running the Agent**

The agent can be initialized in various modes depending on the task requirements.

## **CLI Execution**

Initialize the command line interface:

&nbsp;

* python agent.py \--cli

## **Web GUI Execution**

For a browser-based experience:

&nbsp;

* Launch: python agent.py \--gui \--port 8080

# **Testing & Verification**

To ensure production stability, utilize the Golden Regression Suite. Verify the following capabilities:

&nbsp;

* **Conversational Flow**: Test multi-turn dialogue to ensure context retention.  
* **Tool Execution**: Prompt for a calculation or current time to verify the Gatekeeper Pattern successfully attaches and executes tools.  
* **Code Synthesis**: Request a Python script for data processing to verify Qwen 2.5-Coder performance.

# **References & Knowledge Base**

For further reading on the architectural principles and projects that inspired this system, refer to:

&nbsp;

* [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents) — Insights on agentic design patterns from Anthropic.  
* [500 AI Agents Projects](https://github.com/ashishpatel26/500-AI-Agents-Projects) — A comprehensive list of agent implementations.

&nbsp;
