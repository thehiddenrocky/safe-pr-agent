 1 # Implementation Plan: Autonomous PR Agent with Evaluation Guardrails
    2
    3 ## 1. Objective
    4 Build an AI Agent that autonomously creates pull requests to address specific
      diagnoses/issues, strictly decoupled from the evaluation/merging phase. This two-repo
      architecture directly satisfies the "AI Roots Data Case" requirements by separating the
      **proposer** (the agent) from the **safety/eval boundary** (the existing repository).
    5
    6 ## 2. Architecture: Two Repos, One Story
    7
    8 ### Repo 1: `non-llm-judges` (The Evaluator / Safety Boundary)
    9 *   **Role:** The target repository that the agent modifies, which inherently serves as
      the guardrails.
   10 *   **Enhancements:** We will add a GitHub Actions CI pipeline that automatically runs
      the repository's evaluation scripts (`train_svm.py` or model test scripts) on every
      opened PR.
   11 *   **Safety Control:** The CI will calculate Acceptance Rate, F1 Score,
      Precision/Recall, and Latency. **Crucially, the CI must post the raw numbers
      honestly—including failures or regressions.** We will not filter out bad results.
      Presenting the unvarnished truth, even when the agent gets it wrong, is a key signal of
      engineering maturity. A human reviewer will use these CI results to approve or reject
      the PR (fully utilizing the free tier of GitHub without requiring paid branch protection
      rules).
   12
   13 ### Repo 2: `minimal-pr-agent` (The Proposer)
   14 *   **Role:** The AI application (Python) that reads a trigger, generates a proposed
      code change, and opens a PR with full provenance.
   15 *   **Capabilities:**
   16     *   Listens to specific GitHub Issues on Repo 1 acting as the "diagnosis" (e.g.,
      "Performance regression in SVM model" or "Update TF-IDF vectorizer parameters").
   17     *   Retrieves repository context using a GitHub App token.
   18     *   Generates a fix via Claude/Gemini.
   19     *   Verifies the fix locally in a sandbox.
   20     *   Opens a PR detailing: what was detected, the evidence, what changed, and why.
   21     *   Cannot merge (enforced purely by strictly limiting the GitHub App's token
      permissions to 'Read/Write Pull Requests' but NOT granting merge permissions).
   22
   23 ## 3. The Narrow Class of Faults
   24 The agent will operate on a strict allowlist of issues it is permitted to fix.
   25 *   **Allowed Faults:** Hyperparameter tuning updates, pipeline scaling adjustments
      (e.g., modifying `StandardScaler` to `RobustScaler` in `train_svm.py`), or fixing
      syntax/typing errors in the training scripts.
   26 *   **Enforcement:** If an issue does not match the Pydantic schema for these allowed
      faults, the agent logs the rejection and exits safely.
   27
   28 ## 4. Implementation Steps
   29
   30 ### Phase 1: Establish the Guardrails (Repo 1)
   31 1.  **Evaluation CI:** Write a GitHub Actions `.yml` workflow that triggers on
      `pull_request`. It will run the models, generate the F1/Accuracy/Latency metrics, and
      use the `actions/github-script` to post the evaluation results as a comment on the PR.
      The workflow script will explicitly ensure that failed runs, metric regressions, and
      errors are included in the comment payload to provide an honest, unvarnished view of the
      agent's work. This CI run acts as the primary safety mechanism for human review.
   32
   33 ### Phase 2: Build the Agent (Repo 2)
   34 1.  **Project Setup:** Initialize `minimal-pr-agent` (Python 3.11+, Pydantic, FastAPI
      for webhooks, PyGithub, Anthropic/Google SDK).
   35 2.  **Ingestion & Allowlist:** Create the webhook receiver to listen for new Issues on
      Repo 1. Implement the Pydantic allowlist to filter issues.
   36 3.  **Context Retrieval:** Implement logic to clone Repo 1, extract the files mentioned
      in the issue, and package them into the LLM prompt.
   37 4.  **Generation & Local Verification:** Pass the context to the LLM. Implement a
      subprocess sandbox that applies the diff locally and runs a quick syntax/smoke test
      before proceeding.
   38 5.  **PR Provenance:** Construct the PR payload. The description will automatically
      structure the Diagnosis, Evidence, Fix, and Rationale. Open the PR via PyGithub.
   39
   40 ### Phase 3: The Reviewer Experience & Feedback Loop
   41 1.  **Rejection Handling:** In Repo 2, listen for `pull_request_review` events
      indicating a rejection ("Changes requested").
   42 2.  **Learning Signal:** Extract the reviewer's feedback and store it (locally in a
      JSON/SQLite store for the MVP) to inject as negative constraints into future prompts for
      similar faults.
   43
   44 ## 5. Delivery & Demonstration
   45 *   The README of `minimal-pr-agent` will explicitly detail this architecture,
      emphasizing that the safety boundary is a *design problem* solved by decoupling the
      agent from the evaluator.
   46 *   We will demonstrate the agent by opening an issue on Repo 1, watching the agent open
      a PR, and observing the CI post the evaluation metrics.
