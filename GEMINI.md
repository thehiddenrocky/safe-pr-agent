# Project Overview

This repository serves as the central planning and orchestration workspace for the **Autonomous PR Agent with Evaluation Guardrails** (`ai-coder`) project. The project features a decoupled, two-repository architecture designed to safely propose and evaluate automated code changes.

## Architecture: Two Repos, One Story

1. **Repo 1: `non-llm-judges` (The Evaluator / Safety Boundary)**
   - **Role:** The target repository that the agent modifies.
   - **CI Pipeline:** Evaluates the models (e.g., SVM, model test scripts) on every open PR, calculating Acceptance Rate, F1 Score, Precision/Recall, and Latency.
   - **Safety Boundary:** The CI pipeline automatically and honestly posts the raw results as PR comments. Failed runs or regressions are never filtered out. Human reviewers make the final merge decisions.

2. **Repo 2: `minimal-pr-agent` (The Proposer)**
   - **Role:** A Python-based AI application that reads issue triggers, generates code changes using LLMs, verifies them in a sandbox, and opens a structured PR.
   - **Security:** Decoupled from merging capability. The GitHub App token is restricted to Read/Write Pull Requests, preventing unauthorized merges.

---

# Directory Overview

This directory contains the core strategy and planning documents for the project:
- `plan.md`: The architectural specification detailing the objective, repository roles, narrow class of faults, and execution phases.
- `GEMINI.md`: (This file) Contains the fundamental instructions, conventions, and rules for the workspace.
- `plans/`: Contains approved implementation plans and historical context.

---

# Key Technologies

- **Language:** Python 3.11+
- **Agent Stack:** FastAPI (webhook ingestion), Pydantic (data parsing/allowlisting), PyGithub (PR management), Anthropic/Google LLM SDKs.

---

# Development Conventions & Rules

## 1. Strict Fault Allowlist
The PR agent must operate under a strict allowlist of issues it is permitted to fix:
- Hyperparameter tuning updates.
- Pipeline scaling adjustments (e.g., switching `StandardScaler` to `RobustScaler` in training scripts).
- Syntax/typing fixes in ML scripts.

If an issue does not fit the Pydantic schema for these allowed faults, it must be safely logged as a rejection.

## 2. Unvarnished Metric Transparency
- All CI reporting on Repo 1 must post real, unfiltered results. Regressions, performance dips, or complete failures are crucial feedback signals and must be clearly presented in the PR comments.

## 3. Local Sandbox Verification
- Before any PR is submitted, proposed changes must be evaluated and verified locally inside a safe sandbox environment to prevent syntactically broken PRs.

## 4. PR Provenance
- Every generated PR must include structured evidence detailing:
  - **Diagnosis:** What issue was detected.
  - **Evidence:** The logs or issues analyzed.
  - **Fix:** What code was changed.
  - **Rationale:** Why the change is expected to address the diagnosis.
