#!/usr/bin/env python3
"""
Verification script to test GitHub App authentication and access to a target repository.
Accepts the target repository URL as a command-line argument.
"""

import os
import sys
import argparse

def load_dotenv():
    # Load .env variables manually to avoid external dependencies
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

def main():
    parser = argparse.ArgumentParser(
        description="Verify GitHub App authentication and connection for a target repository."
    )
    parser.add_argument(
        "repo_url",
        type=str,
        help="The clone URL or fullname of the target repository (e.g., https://github.com/owner/repo.git)"
    )
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Import the provider
    try:
        from agent.github_provider import GitRepositoryProvider
    except ImportError:
        print("❌ Error: Could not import GitRepositoryProvider. Ensure you run this from the project root.")
        sys.exit(1)

    print("====================================================")
    print("🔐 TESTING GITHUB APP AUTHENTICATION & ACCESS")
    print("====================================================")
    print(f"Target Repository: {args.repo_url}")
    print(f"App ID:            {os.getenv('GITHUB_APP_ID')}")
    print(f"Installation ID:   {os.getenv('GITHUB_INSTALLATION_ID')}")
    print(f"Private Key Path:  {os.getenv('GITHUB_PRIVATE_KEY_PATH') or os.getenv('GITHUB_PRIVATE_KEY')}")
    print("====================================================")

    try:
        print("🔄 Initiating authentication and testing connection...")
        provider = GitRepositoryProvider(args.repo_url)
        
        if provider.token:
            print("\n✅ SUCCESS!")
            print(f"   - Successfully generated JWT and fetched installation access token.")
            print(f"   - Token acquired: {provider.token[:10]}...")
            print(f"   - Cloned repository to temporary sandbox: {provider.base_path}")
        else:
            print("\n⚠️ WARNING: Standard local clone fallback (credentials are missing from environment).")
            print(f"   - Cloned repository to: {provider.base_path}")
            
        # Clean up temporary directories
        provider.cleanup()
        print("\n🧹 Sandbox directory successfully cleaned up.")
        print("====================================================")
        
    except Exception as e:
        print("\n❌ VERIFICATION FAILED!")
        print("Please check that:")
        print("  1. The GitHub App is active and installed on the target repository.")
        print("  2. Your .env file is correctly configured with GITHUB_APP_ID, GITHUB_INSTALLATION_ID, and GITHUB_PRIVATE_KEY_PATH.")
        print("  3. The private key file exists and matches the App registration.")
        print(f"\nError Details:\n{e}")
        print("====================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
