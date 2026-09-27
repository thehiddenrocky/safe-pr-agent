import unittest
from agent.agent import validate_proposed_changes

class TestPRagentSafetyGates(unittest.TestCase):
    def setUp(self):
        self.allowed_files = ["train_svm.py"]
        self.allowed_patterns = [
            r"^C\s*=\s*[0-9.]+",
            r"^kernel\s*=\s*['\"][a-zA-Z0-9]+['\"]",
            r"^scaler\s*=\s*['\"][a-zA-Z0-9]+['\"]"
        ]
        self.original_content = """# Hyperparameters
C = 1.0
kernel = "rbf"
scaler = "StandardScaler"
print("Model training completed successfully.")
"""

    def test_allowlist_approved_changes(self):
        # Scenario: Valid hyperparameter updates
        modified_content = """# Hyperparameters
C = 10.0
kernel = "linear"
scaler = "RobustScaler"
print("Model training completed successfully.")
"""
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="train_svm.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns
        )
        self.assertTrue(is_valid)
        self.assertIsNone(err_msg)

    def test_reject_unauthorized_file(self):
        # Scenario: Trying to modify an unauthorized file name
        modified_content = "C = 10.0"
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="unauthorized_file.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns
        )
        self.assertFalse(is_valid)
        self.assertIn("is not in the allowed files list", err_msg)

    def test_reject_malicious_code_injection(self):
        # Scenario: Trying to inject malicious system execution code
        modified_content = """# Hyperparameters
C = 10.0
kernel = "rbf"
scaler = "StandardScaler"
import os; os.system("echo Exploit!")
print("Model training completed successfully.")
"""
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="train_svm.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns
        )
        self.assertFalse(is_valid)
        self.assertIn("Unauthorized code modification detected", err_msg)

    def test_reject_unauthorized_hyperparameter(self):
        # Scenario: Trying to edit a hyperparameter/variable not in the allowlist pattern
        modified_content = """# Hyperparameters
C = 10.0
kernel = "rbf"
scaler = "StandardScaler"
unallowed_param = 42
print("Model training completed successfully.")
"""
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="train_svm.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns
        )
        self.assertFalse(is_valid)
        self.assertIn("unallowed_param = 42", err_msg)

    def test_relaxed_mode_approved_changes(self):
        # Scenario: General hyperparameter or code updates are allowed in relaxed mode
        modified_content = """# Hyperparameters
C = 10.0
kernel = "linear"
scaler = "RobustScaler"
gamma = "scale"
random_state = 42
# We tuned hyperparameters successfully
print("Model training completed successfully with new parameters.")
"""
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="train_svm.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns,
            mode="relaxed"
        )
        self.assertTrue(is_valid)
        self.assertIsNone(err_msg)

    def test_relaxed_mode_reject_malicious_code_injection(self):
        # Scenario: In relaxed mode, malicious actions are still blocked
        malicious_contents = [
            self.original_content + "\nimport os; os.system('id')",
            self.original_content + "\nsubprocess.Popen(['ls'])",
            self.original_content + "\neval('1+1')",
            self.original_content + "\nexec('import sys')",
            self.original_content + "\nfrom sys import exit",
        ]
        for mc in malicious_contents:
            is_valid, err_msg = validate_proposed_changes(
                original_content=self.original_content,
                new_content=mc,
                file_name="train_svm.py",
                allowed_files=self.allowed_files,
                allowed_patterns=self.allowed_patterns,
                mode="relaxed"
            )
            self.assertFalse(is_valid, f"Expected content to be blocked: {mc}")
            self.assertIn("Malicious code injection or dangerous operation detected", err_msg)

    def test_relaxed_mode_reject_unauthorized_file(self):
        # Scenario: Relaxed mode still protects file scope boundaries
        modified_content = "C = 10.0"
        is_valid, err_msg = validate_proposed_changes(
            original_content=self.original_content,
            new_content=modified_content,
            file_name="unauthorized_file.py",
            allowed_files=self.allowed_files,
            allowed_patterns=self.allowed_patterns,
            mode="relaxed"
        )
        self.assertFalse(is_valid)
        self.assertIn("is not in the allowed files list", err_msg)


from unittest.mock import patch, MagicMock
from agent.agent import LocalRepositoryProvider
from agent.github_provider import GitRepositoryProvider

class TestIssueDetection(unittest.TestCase):
    def test_local_repository_provider_get_open_issues(self):
        provider = LocalRepositoryProvider(".")
        issues = provider.get_open_issues()
        self.assertEqual(issues, [])

    @patch("agent.github_provider.GitRepositoryProvider._clone_and_checkout")
    @patch("requests.get")
    def test_git_repository_provider_get_open_issues(self, mock_get, mock_clone):
        # Setup mock for GitRepositoryProvider initialization to prevent network/auth calls
        with patch.dict("os.environ", {
            "GITHUB_APP_ID": "12345",
            "GITHUB_INSTALLATION_ID": "67890",
            "GITHUB_PRIVATE_KEY": "fake_private_key"
        }):
            with patch("agent.github_provider.GitHubAppAuthenticator") as mock_auth:
                mock_auth.return_value.get_installation_access_token.return_value = "fake_token"
                
                # Instantiate provider
                provider = GitRepositoryProvider("https://github.com/owner/repo.git")
                
                # Mock response from GitHub Issues API
                mock_response = MagicMock()
                mock_response.json.return_value = [
                    {
                        "number": 1,
                        "title": "Fix issue 1",
                        "body": "Fix details 1",
                        "labels": [{"name": "ai-coder"}],
                        "html_url": "https://github.com/owner/repo/issues/1"
                    },
                    {
                        "number": 2,
                        "title": "A Pull Request issue",
                        "pull_request": {} # Marks this as a PR
                    }
                ]
                mock_get.return_value = mock_response
                
                issues = provider.get_open_issues()
                
                # Should find exactly 1 pure issue (excluding the PR)
                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0]["number"], 1)
                self.assertEqual(issues[0]["title"], "Fix issue 1")
                self.assertEqual(issues[0]["body"], "Fix details 1")
                self.assertEqual(issues[0]["labels"], ["ai-coder"])
                provider.cleanup()


class TestTeeStream(unittest.TestCase):
    def test_tee_stream_redirection(self):
        import io
        from agent.agent import TeeStream

        mock_stdout = io.StringIO()
        mock_log = io.StringIO()

        tee = TeeStream(mock_stdout, [mock_log])
        tee.write("Hello, logging world!\n")
        tee.flush()

        self.assertEqual(mock_stdout.getvalue(), "Hello, logging world!\n")
        self.assertEqual(mock_log.getvalue(), "Hello, logging world!\n")


if __name__ == "__main__":
    unittest.main()
