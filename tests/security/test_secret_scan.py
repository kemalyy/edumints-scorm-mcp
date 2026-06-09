"""tests/security/test_secret_scan.py — Basic secret/key leakage scan.
Checks the repository for common secret patterns (API keys, tokens, etc.).
"""

import os
import re

# Simple patterns for secrets
SECRET_PATTERNS = [
    (r"AIza[0-9A-Za-z-_]{35}", "Google API Key"),
    (r"sk_live_[0-9a-zA-Z]{24}", "Stripe Live Secret Key"),
    (r"sq0csp-[0-9A-Za-z-_]{43}", "Square Access Token"),
    (r"sq0atp-[0-9A-Za-z-_]{22}", "Square OAuth Secret"),
    (r"access_token\$production\$[0-9a-z]{16}\$[0-9a-f]{32}", "Braintree Access Token"),
    (r"amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "Amazon MWS Auth Token"),
    (r"SK[0-9a-fA-F]{32}", "Twilio API Key"),
    (r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8}/[a-zA-Z0-9_]{24}", "Slack Webhook"),
    (r"xox[baprs]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}", "Slack Token"),
    (r"github_pat_[0-9a-zA-Z]{82}", "GitHub Personal Access Token"),
]

IGNORE_EXTENSIONS = {'.pyc', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.min.js', '.zip', '.db'}
IGNORE_DIRS = {'.git', '__pycache__', '.venv', 'node_modules', 'dist', 'build'}

def test_no_secrets_in_repo():
    findings = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if any(file.endswith(ext) for ext in IGNORE_EXTENSIONS):
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for pattern, description in SECRET_PATTERNS:
                        matches = re.findall(pattern, content)
                        if matches:
                            # Filter out false positives in this test file itself
                            if "test_secret_scan.py" in filepath:
                                continue
                            findings.append(f"{description} found in {filepath}")
            except Exception:
                 # Skip files that can't be read
                 pass
    
    assert not findings, f"Secrets found: {', '.join(findings)}"

def test_no_dotenv_files():
    # .env files should not be committed (only .env.example)
    dotenv_files = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        if ".env" in files:
            dotenv_files.append(os.path.join(root, ".env"))
    
    assert not dotenv_files, f"Commited .env files found: {', '.join(dotenv_files)}"
