# Implementation Plan: Simulated Monorepo Setup
    2
    3 ## Objective
    4 Simulate the decoupled two-repo architecture by creating an `evaluator/` folder
      (representing `non-llm-judges`) and an `agent/` folder (representing `minimal-pr-agent`)
      in the current workspace. This will let us develop and test the core agent workflows and
      safety guardrails locally for this weekend project.
    5
    6 **Crucially, the agent must be built generically.** The "target repository" will be
      configurable via a variable/config. For now, it will point to the local `../evaluator/`
      folder, but it should be designed so that swapping to a real remote Git repository
      (e.g., via a git link) requires zero code changes in the core agent logic.
    7
    8 ## Implementation Steps
    9
   10 ### Phase 1: Set up the Evaluator
   11 1. Create directory `evaluator/`.
   12 2. Create `evaluator/train_svm.py`:
   13    - A mock script that simulates training an SVM.
   14    - It will contain parameters (like `C`, `kernel`) that can be tweaked.
   15    - It will output a `metrics.json` file containing mock F1, Precision, Recall, and
      Latency scores.
   16
   17 ### Phase 2: Set up the Agent (Generic Architecture)
   18 1. Create directory `agent/`.
   19 2. Create `agent/config.yaml`:
   20    - A configuration file defining the `target_repo` (currently a local path
      `../evaluator`, later a Git URL) and the allowlist rules (e.g., files and regex patterns
      allowed to change).
   21 3. Create `agent/agent.py`:
   22    - Implement an abstraction `RepositoryProvider` that handles interacting with the
      codebase. If the `target_repo` is local, it just works in that folder. If it's remote,
      it would clone it (we will implement the local part first, but keeping the interface
      generic).
   23    - Define a simple CLI that takes an issue description as input.
   24    - **Ingestion/Allowlist**: Validate the request against `config.yaml`.
   25    - **Generation**: Set up the LLM integration to generate the diff.
   26    - **Sandbox Test**: Run the evaluation command (configured in `config.yaml`) in the
      cloned/local workspace and read the new `metrics.json`.
   27    - **PR Creation**: Print the final PR structure to the console, ready to be swapped
      with a real PyGithub integration later.
   28
   29 ## Verification & Testing
   30 - Run `python evaluator/train_svm.py` manually to ensure it outputs `metrics.json`.
   31 - Run `python agent/agent.py "Test Issue"` to ensure it reads the generic config,
      validates the input, and executes the sandbox test against the configured target
      repository.

