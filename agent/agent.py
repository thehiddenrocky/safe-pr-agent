import os
import sys
import yaml
import re
import json
import subprocess
import argparse
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

# =====================================================================
# 1. Repository Provider Abstraction (Generic Architecture)
# =====================================================================

class RepositoryProvider(ABC):
    """
    Abstract base class representing interactions with the target codebase.
    Decouples the core agent logic from the repository storage backend (Local vs Remote Git).
    """
    @abstractmethod
    def get_file_content(self, file_path: str) -> str:
        """Retrieves the text content of a file."""
        pass

    @abstractmethod
    def write_file_content(self, file_path: str, content: str) -> None:
        """Writes/overwrites content to a file."""
        pass

    @abstractmethod
    def run_command(self, command: str) -> subprocess.CompletedProcess:
        """Runs an evaluation/test command in the repository workspace environment."""
        pass

    @abstractmethod
    def read_metrics(self, metrics_file: str) -> dict:
        """Reads and parses the JSON metrics output from the workspace."""
        pass


class LocalRepositoryProvider(RepositoryProvider):
    """
    Implements RepositoryProvider for a local simulation layout.
    """
    def __init__(self, base_path: str):
        # Resolve path relative to this script's directory if it is a relative path
        if not os.path.isabs(base_path):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.base_path = os.path.abspath(os.path.join(script_dir, base_path))
        else:
            self.base_path = base_path
            
        if not os.path.isdir(self.base_path):
            raise FileNotFoundError(f"Local target repository path not found: {self.base_path}")

    def _resolve_path(self, file_path: str) -> str:
        # Prevent directory traversal
        resolved = os.path.abspath(os.path.join(self.base_path, file_path))
        if not resolved.startswith(self.base_path):
            raise ValueError(f"Access denied: {file_path} is outside repository root.")
        return resolved

    def get_file_content(self, file_path: str) -> str:
        full_path = self._resolve_path(file_path)
        with open(full_path, "r") as f:
            return f.read()

    def write_file_content(self, file_path: str, content: str) -> None:
        full_path = self._resolve_path(file_path)
        with open(full_path, "w") as f:
            f.write(content)

    def run_command(self, command: str) -> subprocess.CompletedProcess:
        # Run command inside the target repository directory
        print(f"[Sandbox] Executing command in '{self.base_path}': {command}")
        return subprocess.run(
            command,
            shell=True,
            cwd=self.base_path,
            capture_output=True,
            text=True
        )

    def read_metrics(self, metrics_file: str) -> dict:
        full_path = self._resolve_path(metrics_file)
        if not os.path.exists(full_path):
            return {}
        with open(full_path, "r") as f:
            return json.load(f)


class GitRepositoryProvider(RepositoryProvider):
    """
    STUB: Future implementation for real Git/GitHub integration.
    Swapping to this requires ZERO changes to the core agent runner because it shares
    the RepositoryProvider interface.
    """
    def __init__(self, clone_url: str, branch: str = "main"):
        self.clone_url = clone_url
        self.branch = branch
        self.local_clone_path = "/tmp/cloned_repo"
        # In a real setup, we would run:
        # subprocess.run(f"git clone {clone_url} {self.local_clone_path}")

    def get_file_content(self, file_path: str) -> str:
        # Fetch file content from the cloned directory
        pass

    def write_file_content(self, file_path: str, content: str) -> None:
        # Modify file locally in clone, stage, commit, push, open PR
        pass

    def run_command(self, command: str) -> subprocess.CompletedProcess:
        # Run command in sandbox or Docker container representing the clone
        pass

    def read_metrics(self, metrics_file: str) -> dict:
        # Read metrics generated in the sandbox
        pass


# =====================================================================
# 2. Config & Validation Rules
# =====================================================================

def load_config() -> dict:
    """Loads YAML configuration for the PR Agent."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def validate_proposed_changes(
    original_content: str,
    new_content: str,
    file_name: str,
    allowed_files: List[str],
    allowed_patterns: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Strict allowlist validation gate.
    Ensures ONLY allowed files are edited, and ONLY lines matching allowed regex patterns are modified.
    """
    # Gate 1: Check if file name is in the allowlist
    if file_name not in allowed_files:
        return False, f"File '{file_name}' is not in the allowed files list: {allowed_files}."

    # Gate 2: Analyze line differences to ensure no unauthorized lines were changed
    original_lines = original_content.splitlines()
    new_lines = new_content.splitlines()

    # Compare lines
    # For a simple, ultra-secure validation on small ML hyperparameter scripts:
    # Ensure any line that was modified or introduced matches one of the allowed patterns.
    compiled_patterns = [re.compile(p) for p in allowed_patterns]

    # Let's perform a simple check:
    # Find all lines in the new content that differ from original content.
    # To keep it extremely robust and clear, we find non-blank lines that are not in the original content.
    original_lines_set = set(original_lines)
    
    modified_lines = []
    for line in new_lines:
        trimmed = line.strip()
        if trimmed and line not in original_lines_set:
            # This is a modified or added line! Let's check if it matches at least one pattern.
            matched = False
            for pattern in compiled_patterns:
                if pattern.search(trimmed):
                    matched = True
                    break
            if not matched:
                return False, f"Unauthorized code modification detected. Line: '{line}' does not match any of the allowed patterns: {allowed_patterns}."

    return True, None


# =====================================================================
# 3. LLM Code Generation Client
# =====================================================================

def generate_fix(issue_desc: str, codebase_context: str, provider_config: dict) -> dict:
    """
    Generates a code change using Gemini or falls back to a deterministic Mock response.
    Returns a JSON payload with file_to_modify, original_code, new_code, and rationale.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # We will fallback to mock generation if the key is missing or if configured
    if provider_config.get("provider") != "gemini" or not api_key:
        print("[LLM Client] GEMINI_API_KEY is not set or provider is set to mock. Falling back to Mock generator.")
        return get_mock_llm_response(issue_desc)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(provider_config.get("model", "gemini-1.5-flash"))
        
        prompt = f"""
You are an autonomous machine learning engineer agent.
Your goal is to propose a safe, targeted modification to a machine learning script to resolve a user-reported issue.

You MUST only suggest edits that fit the strict security rules.
Allowed file to modify: train_svm.py
Allowed changes:
1. Adjusting regularization C (must be assigned like: C = <float>)
2. Modifying kernel (must be assigned like: kernel = "<kernel_type>")
3. Updating scaler (must be assigned like: scaler = "<scaler_type>")

Here is the current content of 'train_svm.py':
```python
{codebase_context}
```

The user issue description is:
"{issue_desc}"

Propose the optimal changes to address this issue and maximize F1-score/Latency balance.
You must return your response STRICTLY as a JSON object with the following fields:
1. "file_to_modify": Must be "train_svm.py"
2. "original_code": The exact multi-line string in the original file that you want to replace. Make sure it contains the variables you want to change.
3. "new_code": The exact replacement string.
4. "explanation": A detailed, professional diagnosis of the issue.
5. "rationale": Why this hyperparameter update is mathematically or procedurally correct.

Example JSON output format:
{{
  "file_to_modify": "train_svm.py",
  "original_code": "C = 1.0\\nkernel = \\"rbf\\"\\nscaler = \\"StandardScaler\\"",
  "new_code": "C = 10.0\\nkernel = \\"linear\\"\\nscaler = \\"RobustScaler\\"",
  "explanation": "Identified performance bottlenecks...",
  "rationale": "RobustScaler handles outliers..."
}}

Ensure that the JSON is valid and do NOT wrap it in any extra markdown other than optionally a json block.
"""
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Parse JSON from markdown code blocks if the LLM wrapped it
        if text.startswith("```"):
            # strip off backticks
            lines = text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            text = "\n".join(lines).strip()
            
        return json.loads(text)

    except Exception as e:
        print(f"[LLM Client] Error calling Gemini API: {e}. Falling back to Mock generator.")
        return get_mock_llm_response(issue_desc)


def get_mock_llm_response(issue_desc: str) -> dict:
    """
    Deterministic mock response simulating an LLM generating hyperparameter modifications
    based on keywords in the issue description.
    """
    issue_lower = issue_desc.lower()
    
    # Initialize defaults (base values from train_svm.py)
    new_c = "1.0"
    new_kernel = '"rbf"'
    new_scaler = '"StandardScaler"'
    explanation = "Standard default hyperparameters configuration."
    rationale = "Maintains baseline model structure."

    if "robustscaler" in issue_lower or "scaler" in issue_lower or "outlier" in issue_lower:
        new_scaler = '"RobustScaler"'
        explanation = "Detected scaling vulnerabilities or potential outliers in the feature distribution."
        rationale = "RobustScaler scales features using statistics that are robust to outliers (IQR), preventing them from skewing the SVM decision boundary."

    if "tune" in issue_lower or "regularization" in issue_lower or "c =" in issue_lower or "c to" in issue_lower or "performance" in issue_lower:
        new_c = "10.0"
        explanation = "Detected sub-optimal regularization boundary. The default C=1.0 is underfitting the training dataset."
        rationale = "Increasing C to 10.0 decreases the margin size, forcing the SVM to classify more training examples correctly, resolving the underfitting."

    if "linear" in issue_lower or "kernel" in issue_lower:
        new_kernel = '"linear"'
        explanation = "Detected latency issues or high complexity using non-linear RBF kernel."
        rationale = "The linear kernel significantly reduces prediction latency and is highly effective for linearly separable feature spaces."

    original_code = 'C = 1.0\nkernel = "rbf"\nscaler = "StandardScaler"'
    new_code = f'C = {new_c}\nkernel = {new_kernel}\nscaler = {new_scaler}'

    return {
        "file_to_modify": "train_svm.py",
        "original_code": original_code,
        "new_code": new_code,
        "explanation": explanation,
        "rationale": rationale
    }


# =====================================================================
# 4. Main Runner Core Loop
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Autonomous PR Agent CLI")
    parser.add_argument("issue", type=str, help="The user-reported issue / diagnosis to solve.")
    args = parser.parse_args()

    print("====================================================")
    print("🤖 STARTING AUTONOMOUS PR AGENT")
    print("====================================================")
    print(f"Issue Triggered: \"{args.issue}\"\n")

    # 1. Load Configurations
    try:
        config = load_config()
        print("[Config] Successfully loaded config.yaml.")
    except Exception as e:
        print(f"[Error] Failed to load config.yaml: {e}")
        sys.exit(1)

    target_config = config.get("target_repo", {})
    allowlist_config = config.get("allowlist", {})
    sandbox_config = config.get("sandbox", {})
    llm_config = config.get("llm", {})

    # 2. Instantiate Repository Provider
    try:
        if target_config.get("type") == "local":
            repo_provider = LocalRepositoryProvider(target_config.get("path"))
            print(f"[Repo] Initialized Local Repository Provider at: {repo_provider.base_path}")
        else:
            # Future swap path
            repo_provider = GitRepositoryProvider(target_config.get("path"))
            print(f"[Repo] Initialized Git Repository Provider for: {repo_provider.clone_url}")
    except Exception as e:
        print(f"[Error] Failed to initialize Repository Provider: {e}")
        sys.exit(1)

    # 3. Retrieve Original Codebase Context & Metrics
    print("\n--- [Step 1: Context Ingestion] ---")
    file_to_read = "train_svm.py" # In future, determined dynamically or by issue
    try:
        original_content = repo_provider.get_file_content(file_to_read)
        print(f"Retrieved content of '{file_to_read}' successfully.")
    except Exception as e:
        print(f"[Error] Failed to retrieve context for file '{file_to_read}': {e}")
        sys.exit(1)

    # Fetch baseline metrics
    print("Fetching baseline evaluation metrics...")
    baseline_metrics = repo_provider.read_metrics(sandbox_config.get("metrics_file"))
    if baseline_metrics:
        print("Baseline Metrics loaded successfully:")
        for k, v in baseline_metrics.items():
            print(f"  {k}: {v}")
    else:
        print("No baseline metrics found. Running evaluator to establish baseline...")
        res = repo_provider.run_command(sandbox_config.get("evaluation_command"))
        if res.returncode != 0:
            print(f"[Error] Failed to run initial evaluation command: {res.stderr}")
            sys.exit(1)
        baseline_metrics = repo_provider.read_metrics(sandbox_config.get("metrics_file"))
        print("Generated and loaded Baseline Metrics:")
        for k, v in baseline_metrics.items():
            print(f"  {k}: {v}")

    # 4. Generate Proposed Fixes (LLM / Mock)
    print("\n--- [Step 2: Proposing Code Changes] ---")
    print("Calling LLM client...")
    proposal = generate_fix(args.issue, original_content, llm_config)
    
    file_to_modify = proposal.get("file_to_modify")
    original_code_block = proposal.get("original_code")
    new_code_block = proposal.get("new_code")
    explanation = proposal.get("explanation")
    rationale = proposal.get("rationale")

    print(f"LLM proposes to modify file: '{file_to_modify}'")
    print(f"Explanation: {explanation}")
    print(f"Rationale: {rationale}")
    print(f"\nDiff Proposal:")
    print(f"Replacing:\n{original_code_block}")
    print(f"\nWith:\n{new_code_block}")

    # 5. Ingestion Gate: Validate against Allowlist rules
    print("\n--- [Step 3: Allowlist Security Gate] ---")
    
    # Let's rebuild the full file content with changes applied to validate
    if original_code_block not in original_content:
        print("[Error] LLM proposed original code block was not found in the original file content. Aborting.")
        sys.exit(1)
        
    modified_content = original_content.replace(original_code_block, new_code_block)
    
    is_valid, validation_error = validate_proposed_changes(
        original_content=original_content,
        new_content=modified_content,
        file_name=file_to_modify,
        allowed_files=allowlist_config.get("allowed_files", []),
        allowed_patterns=allowlist_config.get("allowed_patterns", [])
    )

    if not is_valid:
        print(f"❌ [Security Reject] Proposed changes failed the strict allowlist guardrail!")
        print(f"Reason: {validation_error}")
        print("Aborting. No changes were applied.")
        sys.exit(1)
    else:
        print("✅ [Security Approved] Proposed changes successfully passed all allowlist guardrails!")

    # 6. Apply Changes to Sandbox
    print("\n--- [Step 4: Sandbox Application & Verification] ---")
    print("Applying changes to the sandbox repository...")
    try:
        repo_provider.write_file_content(file_to_modify, modified_content)
    except Exception as e:
        print(f"[Error] Failed to write changes to file: {e}")
        # Attempt to restore just in case
        sys.exit(1)

    # 7. Execute Local Verification Command
    print("Running sandbox evaluation command to calculate new metrics...")
    eval_res = repo_provider.run_command(sandbox_config.get("evaluation_command"))
    if eval_res.returncode != 0:
        print(f"❌ [Sandbox Error] Evaluation command crashed or failed!")
        print(f"Exit code: {eval_res.returncode}")
        print(f"Error output:\n{eval_res.stderr}")
        
        # Roll back changes immediately to keep sandbox pristine!
        print("Rolling back changes to keep sandbox pristine...")
        repo_provider.write_file_content(file_to_modify, original_content)
        sys.exit(1)

    # Load new metrics
    new_metrics = repo_provider.read_metrics(sandbox_config.get("metrics_file"))
    print("\nNew Evaluation Metrics:")
    for k, v in new_metrics.items():
        print(f"  {k}: {v}")

    # Roll back changes to target repo after verification is complete
    # In a real system, the changes would stay in a dedicated branch, but in our local simulation,
    # rolling back keeps the target repository clean for the next run.
    print("\nRolling back sandbox changes to keep target repository clean...")
    repo_provider.write_file_content(file_to_modify, original_content)

    # 8. Unvarnished Metric Transparency & PR Provenance Output
    print("\n====================================================")
    print("📋 GENERATED PULL REQUEST PAYLOAD (PROVENANCE)")
    print("====================================================")
    
    # Compare metrics
    comparison_table = ""
    for k in baseline_metrics.keys():
        b_val = baseline_metrics[k]
        n_val = new_metrics.get(k, "N/A")
        diff = ""
        if isinstance(b_val, (int, float)) and isinstance(n_val, (int, float)):
            diff_val = n_val - b_val
            diff = f"{'+' if diff_val >= 0 else ''}{round(diff_val, 4)}"
        comparison_table += f"| {k:<12} | {b_val:<10} | {n_val:<10} | {diff:<10} |\n"

    pr_title = f"Autonomous Fix: Tuning Hyperparameters for SVM"
    pr_body = f"""### 🤖 Autonomous PR Proposal

An automated ML adjustment has been proposed to address the reported issue.

#### 🎯 Diagnosis & Evidence
* **Issue Trigger:** "{args.issue}"
* **Original Metrics**: Loaded from `metrics.json`
* **Proposed Adjustment**: Evaluated in sandbox environment

#### 📊 Performance Metric Transparency (Unvarnished Truth)
| Metric       | Baseline   | Sandbox    | Delta      |
| :---         | :---       | :---       | :---       |
{comparison_table}
*Note: These metrics are honest and unvarnished, generated directly by the repository's evaluation runner. Human verification is requested before merging.*

#### 🛠 Applied Fix
File modified: `{file_to_modify}`
```python
<<<<
{original_code_block}
====
{new_code_block}
>>>>
```

#### 💡 Rationale
{rationale}

---
*Created by Autonomous PR Agent System.*
"""
    print(f"PR Title: {pr_title}")
    print("\nPR Body:")
    print(pr_body)
    print("====================================================")
    print("🎉 PROCESS COMPLETED SUCCESSFULLY!")
    print("====================================================")


if __name__ == "__main__":
    main()
