# 🤖 Autonomous PR Agent with Evaluation Guardrails

An autonomous, franchise-ready, and repository-agnostic PR Agent that safely proposes, verifies, and publishes software and model updates with unvarnished metrics transparency.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![LLM: Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-orange.svg)](https://ai.google.dev/)
[![Arch: Decoupled](https://img.shields.io/badge/Architecture-Decoupled-green.svg)](#🏛️-architecture-two-repos-one-story)

This project is built to overcome **"The Technician's Trap"** (from *The E-Myth Revisited* by Michael E. Gerber)—engineering a self-sustaining system that executes end-to-end without requiring human technical intervention.

---

## 💡 Repository Scope & Demonstration Design

> [!NOTE]
> **This codebase is fully generic and repository-agnostic.**
> While the default configuration is set up to target `non-llm-judges` (a machine learning model tuning pipeline) for concrete, end-to-end demonstration and validation, you can target **any repository** by modifying `agent/config.yaml`. No agent logic is hard-coded to any specific codebase.

---

## 🏛️ Architecture: Two Repos, One Story

To enforce strict security, sandboxed isolation, and honest evaluation, the project features a decoupled, two-repository architecture:

```
                  ┌────────────────────────────────────────┐
                  │                                        │
                  │    Proposer Agent (minimal-pr-agent)   │
                  │   (Generic, repository-agnostic core)  │
                  │                                        │
                  └──────────────────┬─────────────────────┘
                                     │
                        Secure API   │   Opens PR with
                       Auth (GH App) │   Unvarnished Metrics
                                     ▼
                  ┌────────────────────────────────────────┐
                  │                                        │
                  │     Evaluator Target (Any Target Repo) │
                  │     (Demonstrated via non-llm-judges)  │
                  │                                        │
                  └────────────────────────────────────────┘
```

### 1. Repo 1: The Proposer — `minimal-pr-agent` (This Repo)
* **Generic Agent Core:** Identifies required improvements, executes local sandbox validations, generates precise modifications using Google's Gemini LLM SDK, and publishes structured, evidence-backed Pull Requests.
* **Security Decoupling:** Fully decoupled from merging capability. The GitHub App token is restricted exclusively to read/write pull requests, preventing unauthorized self-merges.
* **Configurable Guardrails:** Restricts editing to specific allowlisted files and patterns via `config.yaml` to prevent remote code execution or malicious payloads.

### 2. Repo 2: The Evaluator — Target Repository (e.g., `non-llm-judges`)
* **Target Environment:** The repository hosting the application code, ML training pipelines, datasets, or unit/integration tests.
* **CI Validation Pipeline:** Automatically evaluates every incoming PR, calculating metrics like Acceptance Rate, F1-Score, Precision, Recall, and Latency.
* **Safety Boundary:** Real, unvarnished performance results are automatically posted back as PR comments. Human reviewers make the final merge decisions.

---

## ⚙️ Generic & Configurable Design (How to Customize)

The entire agent behavior is driven by `agent/config.yaml`. To point this agent at a completely different codebase, simply adjust these keys:

```yaml
# agent/config.yaml
target_repo:
  type: "remote"
  path: "https://github.com/your-org/your-target-repo.git"  # Any target git repository

allowlist:
  mode: "relaxed" # 'strict' (exact regex lines only) or 'relaxed' (allow safe file modifications)
  allowed_files:
    - "src/config_file.json"                                # Target files the agent is allowed to edit
  allowed_patterns:
    - "^threshold\\s*=\\s*[0-9.]+"                          # Allowed regex modifications

sandbox:
  evaluation_command: "pytest tests/test_behavior.py"       # Local sandbox verification command
  metrics_file: "test-results.json"                         # File to scrape performance/metrics from
```

---

## 📂 Directory Layout

```
.
├── GEMINI.md                    # System rules, design boundaries, and constraints
├── README.md                    # Main overview and setup guide (this file)
├── readme-challenges-resolution.md # Deep-dive into solved technical issues
├── verify_connection.py         # Utility to verify GitHub App authentication
├── agent/                       # Core Agent Application logic
│   ├── agent.py                 # Main orchestration loop & local sandbox
│   ├── github_provider.py       # GitHub API integration & Remote sandbox
│   ├── config.yaml              # App config (target repo, file rules, regex filters)
│   └── test_agent.py            # Unit tests for the agent components
├── credentials/                 # Secure storage for App keys (gitignored)
│   └── *.private-key.pem        # GitHub App Private Key PEM
├── evaluator/                   # Local simulation space
└── venv/                        # Local Python Virtual Environment
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- Python 3.11+ (Python 3.14 recommended/tested)
- macOS (darwin) or Linux environment

### 2. Set Up the Virtual Environment
Clone this repository and create the virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r agent/requirements.txt   # If requirements file exists, or:
# Install core dependencies:
pip install pygithub pydantic google-generativeai python-dotenv pyyaml
# Install sandbox evaluation dependencies:
pip install mlflow scikit-learn pandas numpy xgboost lightgbm
```

### 3. Setup Environment Variables
Create a `.env` file in the root directory:

```ini
# GitHub App Authentication
GITHUB_APP_ID="5072613"
GITHUB_INSTALLATION_ID="164783272"
GITHUB_PRIVATE_KEY_PATH="credentials/ml-tuning-pr-agent.2026-09-25.private-key.pem"

# Gemini LLM API Key
GEMINI_AI_KEY="your-google-gemini-api-key-here"
```

---

## 🚀 Execution & Usage

The agent can be run locally to evaluate baseline metrics, propose modifications (such as changing hyperparameters or hyperparameter scalers), verify them inside an isolated workspace sandbox, and publish the pull request.

To trigger an end-to-end execution requesting a change to `RobustScaler` on the configured remote evaluator repository:

```bash
PYTHONPATH=. venv/bin/python3 agent/agent.py "RobustScaler"
```

### What Happens Behind the Scenes:
1. **App Verification:** Authenticates with GitHub using the App installation ID and private key.
2. **Remote Ingest:** Clones the remote repository (`thehiddenrocky/non-llm-judges` by default) into a temporary workspace.
3. **Baseline Run:** Executes `train_svm.py` dynamically using `sys.executable` to run inside the correct virtualenv, then scrapes current metrics.
4. **Code Generation:** Queries Google Gemini using strict prompt boundaries to propose the modification.
5. **Security Allowlist Gate:** Diffs are validated against allowlisted regular expressions (e.g., matching scaler modifications only) to prevent malicious code injection.
6. **Sandbox Verification:** Executes the modified code to verify stability and parse updated metrics.
7. **PR Submission:** Creates a remote branch, pushes changes, and creates a beautifully formatted PR featuring unvarnished metrics.

---

## 🔍 Deep-Dive & Troubleshooting

For a detailed walkthrough of technical challenges encountered during development—including environment load barriers, virtualenv sandbox routing, and parsing raw stdout metrics—see:

👉 **[readme-challenges-resolution.md](readme-challenges-resolution.md)**

---

## 🏆 Proof of Success

Our end-to-end remote execution successfully generated **Pull Request #2** on the demonstration target repository with fully populated comparative metrics:

🔗 **[Live Pull Request #2 on target repository](https://github.com/thehiddenrocky/non-llm-judges/pull/2)**
