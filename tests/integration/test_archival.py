#!/usr/bin/env python3
"""
Integration test for email archival.

Reads the first rule from integration-test-config.yaml and:
1. Finds 2 emails matching the rule that are older than inbox_days + 1
2. Adds the configured required_label to them
3. Runs gmail_manager
4. Verifies emails were archived (required_label removed)
"""

import subprocess
import json
import os
import sys
import re
import yaml
from pathlib import Path
from datetime import datetime

EXPECTED_EMAIL_COUNT = 2
CONFIG_PATH = Path(__file__).parent / 'integration-test-config.yaml'


def load_config():
    """Load integration test config"""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run_gwsa(args: list) -> tuple:
    """Run gwsa command and return stdout, stderr, returncode"""
    result = subprocess.run(['gwsa'] + args, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def search_emails(query: str) -> list:
    """Search for emails using gwsa"""
    stdout, stderr, rc = run_gwsa(['mail', 'search', query, '--format', 'full'])
    if rc != 0 or not stdout.strip():
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return []


def add_label(email_id: str, label: str) -> bool:
    stdout, stderr, rc = run_gwsa(['mail', 'label', email_id, label])
    return rc == 0


def remove_label(email_id: str, label: str) -> bool:
    stdout, stderr, rc = run_gwsa(['mail', 'label', email_id, label, '--remove'])
    return rc == 0


def parse_email_date(date_str: str) -> datetime:
    """Parse email date string to datetime"""
    date_part = re.sub(r'\s+\([A-Z]+\)$', '', date_str)
    for tz in [' GMT', ' UTC']:
        if tz in date_part:
            date_part = date_part.split(tz)[0]
    date_part = re.sub(r'\s+[+-]\d{4}$', '', date_part).strip()
    try:
        return datetime.strptime(date_part, '%a, %d %b %Y %H:%M:%S')
    except ValueError:
        return datetime.strptime(date_part, '%d %b %Y %H:%M:%S')


def get_email_age_days(email: dict) -> int:
    try:
        return (datetime.now() - parse_email_date(email.get('date', ''))).days
    except Exception:
        return 0


def build_search_query(rule: dict, min_age_days: int) -> str:
    """Build Gmail search query from rule match criteria"""
    parts = []
    match = rule.get('match', {})

    if 'sender' in match:
        # Convert regex to simple search term
        sender = match['sender'].replace('\\.', '.').replace('\\', '')
        parts.append(f'from:{sender}')

    if 'subject' in match:
        # Extract first term from regex for search
        subject = match['subject']
        # Handle simple patterns, extract first meaningful term
        subject = re.sub(r'[\\()|\[\].*+?^$]', ' ', subject).split()[0] if subject else ''
        if subject:
            parts.append(f'subject:"{subject}"')

    parts.append(f'older_than:{min_age_days}d')
    return ' '.join(parts)


def main():
    config = load_config()
    required_label = config.get('required_label', 'Test')
    rules = config.get('rules', [])

    if not rules:
        print("ERROR: No rules in config")
        return 1

    rule = rules[0]
    inbox_days = rule.get('inbox_days', 3)
    min_age_days = inbox_days + 1

    print(f"Testing rule: {rule.get('name')}")
    print(f"Required label: {required_label}")
    print(f"Emails must be older than {min_age_days} days")

    # Clear any existing test labels
    existing = search_emails(f'label:{required_label}')
    if existing:
        print(f"\nClearing {len(existing)} existing emails with '{required_label}' label...")
        for email in existing:
            remove_label(email['id'], required_label)

    # Find matching emails
    query = build_search_query(rule, min_age_days)
    print(f"\nSearching: {query}")
    emails = search_emails(query)

    if len(emails) < EXPECTED_EMAIL_COUNT:
        print(f"ERROR: Found only {len(emails)} emails, need {EXPECTED_EMAIL_COUNT}")
        return 1

    # Sort by age and take oldest
    emails.sort(key=lambda e: get_email_age_days(e), reverse=True)
    selected = emails[:EXPECTED_EMAIL_COUNT]

    print(f"\nSelected {EXPECTED_EMAIL_COUNT} emails:")
    setup_ids = []
    for email in selected:
        print(f"  {email['id']}: {email.get('subject', '')[:50]} ({get_email_age_days(email)} days old)")
        if add_label(email['id'], required_label):
            setup_ids.append(email['id'])

    if len(setup_ids) != EXPECTED_EMAIL_COUNT:
        print("ERROR: Failed to label all emails")
        return 1

    # Run gmail_manager
    print(f"\nRunning gmail_manager...")
    env = os.environ.copy()
    env['GMAIL_MANAGER_CONFIG'] = str(CONFIG_PATH)
    project_root = Path(__file__).parent.parent.parent

    result = subprocess.run(
        [sys.executable, 'gmail_manager.py', '--limit', '5'],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True
    )
    print(result.stdout)

    # Verify archival
    print("\nVerifying archival...")
    remaining = {e['id'] for e in search_emails(f'label:{required_label}')}

    success = True
    for email_id in setup_ids:
        if email_id in remaining:
            print(f"  FAIL: {email_id} still has label")
            success = False
        else:
            print(f"  OK: {email_id} archived")

    print("\n" + ("TEST PASSED" if success else "TEST FAILED"))
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
