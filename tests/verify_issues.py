#!/usr/bin/env python3
"""
Verification script to test fetching open issues from the target repository
using the GitHub App token and permissions.
"""

import os
import sys
import yaml
import requests

def load_dotenv():
    # Load .env variables manually
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

def main():
    load_dotenv()

    # Ensure the project root is in sys.path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Import the provider
    try:
        from agent.github_provider import GitRepositoryProvider
    except ImportError:
        print("❌ Error: Could not import GitRepositoryProvider. Ensure you run this from the project root.")
        sys.exit(1)

    # Load target repo URL from config.yaml
    config_path = os.path.join(project_root, "agent/config.yaml")
    if not os.path.exists(config_path):
        print(f"❌ Error: {config_path} not found.")
        sys.exit(1)
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    target_repo_url = config.get("target_repo", {}).get("path")
    if not target_repo_url:
        print("❌ Error: target_repo.path not found in agent/config.yaml")
        sys.exit(1)

    print("====================================================")
    print("📋 TESTING GITHUB APP ISSUES ACCESS")
    print("====================================================")
    print(f"Target Repository URL: {target_repo_url}")
    print("====================================================")

    try:
        print("🔄 Authenticating and fetching repository metadata...")
        # Initialize GitRepositoryProvider to authenticate
        provider = GitRepositoryProvider(target_repo_url)
        
        if not provider.token:
            print("\n❌ AUTHENTICATION FAILED!")
            print("Could not obtain a GitHub App installation access token.")
            print("Please check that GITHUB_APP_ID, GITHUB_INSTALLATION_ID, and GITHUB_PRIVATE_KEY_PATH are configured correctly in .env.")
            provider.cleanup()
            sys.exit(1)
            
        owner = provider.owner
        repo_name = provider.repo_name
        
        print(f"✅ Successfully authenticated as GitHub App.")
        print(f"🔄 Querying open issues for {owner}/{repo_name}...")
        
        # Query issues REST API
        url = f"https://api.github.com/repos/{owner}/{repo_name}/issues"
        headers = {
            "Authorization": f"Bearer {provider.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        response = requests.get(url, headers=headers, params={"state": "open"})
        response.raise_for_status()
        
        issues = response.json()
        
        # Clean up sandbox directory cloned by GitRepositoryProvider initializer
        provider.cleanup()
        
        # Filter out pull requests (GitHub includes PRs in the Issues API)
        pure_issues = [i for i in issues if "pull_request" not in i]
        
        print(f"\nFound {len(pure_issues)} open issue(s):")
        print("-" * 50)
        
        if not pure_issues:
            print("No open issues found.")
            print("Try creating a test issue on your repository to verify!")
        else:
            for idx, issue in enumerate(pure_issues, 1):
                labels = [label["name"] for label in issue.get("labels", [])]
                label_str = f" [{', '.join(labels)}]" if labels else ""
                print(f"{idx}. #{issue['number']}: {issue['title']}{label_str}")
                print(f"   Created by: {issue.get('user', {}).get('login')}")
                print(f"   Link: {issue.get('html_url')}")
                print("-" * 50)
                
        print("\n✅ VERIFICATION COMPLETED SUCCESSFULLY!")
        print("The GitHub App has correct permissions to read issues!")
        print("====================================================")
        
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED!")
        print(f"Error Details: {e}")
        print("====================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
