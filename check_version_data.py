"""
Check version data from API.
"""

import requests
from pathlib import Path
import os
import json


def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path.cwd() / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value


load_env_file()

username = os.environ.get('TRIPTIC_AUTH_USERNAME')
password = os.environ.get('TRIPTIC_AUTH_PASSWORD')

response = requests.get(
    'https://triptic-daveey.fly.dev/asset-group/bird',
    auth=(username, password)
)

if response.ok:
    data = response.json()
    print("Bird asset group - LEFT screen versions:")
    print("=" * 80)
    for i, version in enumerate(data['left']['versions'], 1):
        print(f"\nVersion {i}:")
        print(f"  Content UUID: {version['content']}")
        print(f"  Version UUID: {version['version_uuid']}")
        print(f"  Prompt: {version['prompt'][:100]}...")
    print("\n" + "=" * 80)
    print(f"\nCurrent version UUID: {data['left']['current_version_uuid']}")
else:
    print(f"Error: HTTP {response.status_code}")
    print(response.text)
