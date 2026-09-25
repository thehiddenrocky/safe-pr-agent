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

if __name__ == "__main__":
    unittest.main()
