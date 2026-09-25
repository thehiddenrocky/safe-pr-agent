import os
import sys
import re
import json
import time
import base64
import tempfile
import shutil
import subprocess
import requests
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod

# Import Cryptography components for RS256 JWT signing
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# Handle importing RepositoryProvider relative to package context
try:
    from agent.agent import RepositoryProvider
except ImportError:
    try:
        from agent import RepositoryProvider
    except ImportError:
        # Fallback if executed directly from the directory
        class RepositoryProvider(ABC):
            @abstractmethod
            def get_file_content(self, file_path: str) -> str: pass
            @abstractmethod
            def write_file_content(self, file_path: str, content: str) -> None: pass
            @abstractmethod
            def run_command(self, command: str) -> subprocess.CompletedProcess: pass
            @abstractmethod
            def read_metrics(self, metrics_file: str) -> dict: pass


def load_dotenv():
    """Loads environment variables from .env file at workspace root or packaging directories."""
    possible_paths = [
        ".env",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".env")),
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
            break


class GitHubAppAuthenticator:
    """
    Handles authentication as a GitHub App.
    Generates a RS256 signed JSON Web Token (JWT) and uses it to request
    an installation access token for interacting with repository APIs.
    """
    def __init__(self, app_id: str, private_key_pem: bytes, installation_id: str):
        self.app_id = str(app_id).strip()
        self.private_key_pem = private_key_pem
        self.installation_id = str(installation_id).strip()

    def generate_jwt(self) -> str:
        """
        Generates a RS256 JWT signed with the App's private key.
        """
        header = {"alg": "RS256", "typ": "JWT"}
        now = int(time.time())
        # GitHub JWTs are valid for up to 10 minutes (600 seconds)
        # We start 60s in the past to account for minor clock drift
        payload = {
            "iat": now - 60,
            "exp": now + 540,
            "iss": int(self.app_id)
        }

        def b64_encode(data: dict) -> str:
            json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
            return base64.urlsafe_b64encode(json_bytes).decode('utf-8').rstrip('=')

        encoded_header = b64_encode(header)
        encoded_payload = b64_encode(payload)
        signing_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')

        # Load private key using cryptography
        private_key = serialization.load_pem_private_key(
            self.private_key_pem,
            password=None,
            backend=default_backend()
        )

        # Sign using RS256
        signature = private_key.sign(
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        encoded_signature = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('=')
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

    def get_installation_access_token(self) -> str:
        """
        Exchanges the JWT for an installation access token.
        """
        jwt_token = self.generate_jwt()
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()["token"]


class GitRepositoryProvider(RepositoryProvider):
    """
    Production implementation of RepositoryProvider using a modular GitHub App flow.
    Clones the repository locally using the installation token, enables local execution of
    sandbox tests, and opens a structured PR when the modifications are verified.
    """
    def __init__(self, clone_url: str, branch: Optional[str] = None):
        load_dotenv()
        self.clone_url = clone_url
        self.owner, self.repo_name = self._parse_repo_fullname(clone_url)
        
        # Load GitHub App Credentials from env/config
        self.app_id = os.getenv("GITHUB_APP_ID")
        self.installation_id = os.getenv("GITHUB_INSTALLATION_ID")
        
        private_key_source = os.getenv("GITHUB_PRIVATE_KEY_PATH") or os.getenv("GITHUB_PRIVATE_KEY")
        self.private_key_pem = self._load_private_key(private_key_source) if private_key_source else None

        # Authenticate and obtain installation token
        if self.app_id and self.installation_id and self.private_key_pem:
            print("[GitHub App] Credentials found. Initiating GitHub App authentication...")
            self.authenticator = GitHubAppAuthenticator(self.app_id, self.private_key_pem, self.installation_id)
            self.token = self.authenticator.get_installation_access_token()
            print("[GitHub App] Successfully authenticated. Obtained installation access token.")
        else:
            print("[Warning] GitHub App credentials missing from environment. Standard unauthenticated/local clone fallback.")
            self.token = None
            self.authenticator = None

        # Create unique branch name for the fix
        timestamp = int(time.time())
        self.branch = branch or f"auto-fix-svm-{timestamp}"
        
        # Setup temporary local sandbox directory for operations
        self.base_path = tempfile.mkdtemp(prefix="agent-sandbox-")
        print(f"[Repo] Sandbox directory established at: {self.base_path}")
        
        # Clone repository
        self._clone_and_checkout()

    def _load_private_key(self, source: str) -> bytes:
        if os.path.exists(source):
            with open(source, "rb") as f:
                return f.read()
        if "\\n" in source:
            source = source.replace("\\n", "\n")
        return source.encode("utf-8") if isinstance(source, str) else source

    def _parse_repo_fullname(self, clone_url: str) -> Tuple[str, str]:
        """
        Parses owner and repository name from various GitHub URL formats.
        """
        # Formats:
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        # owner/repo
        cleaned = clone_url.replace(".git", "")
        if "github.com/" in cleaned:
            parts = cleaned.split("github.com/")[-1].split("/")
        elif "github.com:" in cleaned:
            parts = cleaned.split("github.com:")[-1].split("/")
        else:
            parts = cleaned.split("/")
        
        if len(parts) >= 2:
            return parts[0], parts[1]
        raise ValueError(f"Could not parse owner and repository from clone URL: {clone_url}")

    def _clone_and_checkout(self) -> None:
        """
        Clones the target repository and checks out the target/feature branch.
        """
        if self.token:
            # Inject token in clone URL for secure, transparent git operations
            authenticated_url = f"https://x-access-token:{self.token}@github.com/{self.owner}/{self.repo_name}.git"
        else:
            authenticated_url = self.clone_url

        print(f"[Git] Cloning repository '{self.owner}/{self.repo_name}'...")
        # Clone repository into base_path
        clone_res = subprocess.run(
            ["git", "clone", authenticated_url, "."],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        if clone_res.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {clone_res.stderr}")

        # Find default branch
        default_branch = self._get_default_branch()
        print(f"[Git] Repository cloned. Default branch is: '{default_branch}'")

        # Create and checkout feature branch
        print(f"[Git] Checking out new feature branch: '{self.branch}'")
        checkout_res = subprocess.run(
            ["git", "checkout", "-b", self.branch],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        if checkout_res.returncode != 0:
            raise RuntimeError(f"Failed to create branch '{self.branch}': {checkout_res.stderr}")

    def _get_default_branch(self) -> str:
        """
        Determines the default branch of the cloned repo.
        """
        res = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            # Typically returns "refs/remotes/origin/main"
            match = re.search(r"refs/remotes/origin/(.+)", res.stdout.strip())
            if match:
                return match.group(1)
        
        # Fallback to checking active local branch
        res2 = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        return res2.stdout.strip() or "main"

    def _resolve_path(self, file_path: str) -> str:
        resolved = os.path.abspath(os.path.join(self.base_path, file_path))
        if not resolved.startswith(self.base_path):
            raise ValueError(f"Access denied: {file_path} is outside repository root.")
        return resolved

    def get_file_content(self, file_path: str) -> str:
        full_path = self._resolve_path(file_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def write_file_content(self, file_path: str, content: str) -> None:
        full_path = self._resolve_path(file_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    def run_command(self, command: str) -> subprocess.CompletedProcess:
        # Replace python3 or python command prefix with the active sys.executable
        if command.startswith("python3 "):
            command = f"{sys.executable} {command[8:]}"
        elif command.startswith("python "):
            command = f"{sys.executable} {command[7:]}"
            
        print(f"[Sandbox] Running sandbox command in clone: {command}")
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
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def push_and_open_pr(self, pr_title: str, pr_body: str) -> dict:
        """
        Stages and commits modifications, pushes the feature branch to GitHub,
        and submits a Pull Request using the GitHub App installation token.
        """
        if not self.token:
            raise RuntimeError("Cannot open PR without valid GitHub App authentication.")

        # 1. Configure git user locally in the sandbox clone
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=self.base_path)
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=self.base_path)

        # 2. Stage and commit changes
        print("[Git] Staging changes in local clone...")
        subprocess.run(["git", "add", "."], cwd=self.base_path)
        
        print("[Git] Committing changes...")
        commit_res = subprocess.run(
            ["git", "commit", "-m", "🤖 auto-tuned model hyperparameters and scaling"],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout:
            raise RuntimeError(f"Git commit failed: {commit_res.stderr}")

        # 3. Push branch to remote
        print(f"[Git] Pushing feature branch '{self.branch}' to remote origin...")
        push_res = subprocess.run(
            ["git", "push", "origin", self.branch],
            cwd=self.base_path,
            capture_output=True,
            text=True
        )
        if push_res.returncode != 0:
            raise RuntimeError(f"Git push failed: {push_res.stderr}")

        # 4. Open Pull Request via GitHub REST API
        print("[GitHub API] Submitting Pull Request...")
        default_branch = self._get_default_branch()
        url = f"https://api.github.com/repos/{self.owner}/{self.repo_name}/pulls"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        payload = {
            "title": pr_title,
            "body": pr_body,
            "head": self.branch,
            "base": default_branch
        }

        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            pr_data = response.json()
            print(f"🎉 PR successfully opened! URL: {pr_data['html_url']}")
            return pr_data
        else:
            print(f"❌ Failed to open PR! Status code: {response.status_code}")
            print(f"Response: {response.text}")
            raise RuntimeError(f"GitHub API returned error: {response.text}")

    def cleanup(self) -> None:
        """
        Deletes the local temporary sandbox directory.
        """
        if os.path.exists(self.base_path):
            print(f"[Repo] Cleaning up sandbox directory: {self.base_path}")
            shutil.rmtree(self.base_path)
