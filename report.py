#!/usr/bin/env python3
"""
Report generator for processed emails JSON file.

Usage:
  python report.py processed_2025-11-28_1948.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from table_formatter import format_rule_summary_table, format_email_details_table
from app_config import GMAIL_MANAGER_DATA_DIR


def load_processed_file(filename: str) -> dict:
    """Load and parse processed JSON file"""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)


def print_rule_summary(data: dict) -> None:
    """Print rule-level summary table"""
    rules = data.get('rule_statistics', [])

    # Sort rules: found > 0 first (descending), then found = 0
    rules_with_matches = [r for r in rules if r['emails_found'] > 0]
    rules_without_matches = [r for r in rules if r['emails_found'] == 0]

    # Sort by emails_found descending within each group
    rules_with_matches.sort(key=lambda r: r['emails_found'], reverse=True)
    sorted_rules = rules_with_matches + rules_without_matches

    # Calculate totals
    totals = {
        'emails_found': data.get('total_emails_found', 0),
        'emails_processed': data.get('total_emails_processed', 0),
        'emails_labeled': sum(r['emails_labeled'] for r in rules),
        'emails_marked_important': sum(r['emails_marked_important'] for r in rules),
        'emails_archived': sum(r['emails_archived'] for r in rules)
    }

    table = format_rule_summary_table(sorted_rules, totals, "Rule Summary")
    print(table)


def print_email_details(data: dict) -> None:
    """Print detailed email-by-email breakdown"""
    emails = data.get('emails', [])
    table = format_email_details_table(emails)
    print(table)


def print_failed_emails(data: dict) -> None:
    """Print failed emails that encountered errors during processing"""
    failed_emails = data.get('failed_emails', [])
    if not failed_emails:
        return

    print("\n" + "=" * 110)
    print("Failed Emails")
    print("=" * 110)
    print(f"{'Email ID':<20} {'Rule':<40} {'Subject':<30} {'Error':<20}")
    print("-" * 110)

    for email in failed_emails:
        email_id = email.get('email_id', '???')[:20]
        rule = email.get('rule', '')[:40]
        subject = email.get('subject', '')[:30]
        error = email.get('error', '')[:20]
        print(f"{email_id:<20} {rule:<40} {subject:<30} {error:<20}")

    print("=" * 110)


def print_summary(data: dict) -> None:
    """Print top-level summary info"""
    print("\n" + "=" * 110)
    print("Processing Summary")
    print("=" * 110)

    started = data.get('started_at', 'Unknown')
    completed = data.get('completed_at', 'Unknown')
    limit = data.get('limit')
    emails_evaluated = data.get('emails_evaluated', 0)
    emails_matched = data.get('emails_matched', 0)
    emails_unmatched = data.get('emails_unmatched', 0)
    total_rule_matches = data.get('total_rule_matches', 0)
    total_actions_taken = data.get('total_actions_taken', 0)
    # Fallback for old JSON format
    if total_rule_matches == 0:
        total_rule_matches = data.get('total_emails_found', 0)
    if total_actions_taken == 0:
        total_actions_taken = data.get('total_emails_processed', 0)

    print(f"Started:            {started}")
    print(f"Completed:          {completed}")
    if limit:
        print(f"Limit:              {limit} emails")
    print(f"Emails Evaluated:   {emails_evaluated}")
    print(f"Emails Matched:     {emails_matched} (matched 1+ rules)")
    print(f"Emails Unmatched:   {emails_unmatched}")
    print(f"Total Rule Matches: {total_rule_matches}")
    print(f"Total Actions:      {total_actions_taken}")
    print("=" * 110)


def generate_report(data: dict) -> None:
    """Generate complete report from processed data dict"""
    print_summary(data)
    print_rule_summary(data)
    print_email_details(data)
    print_failed_emails(data)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python report.py <processed_json_file>")
        print("\nExample:")
        print("  python report.py processed_2025-11-28_1948.json")
        sys.exit(1)

    filename = sys.argv[1]
    data = load_processed_file(filename)

    # Print all reports
    generate_report(data)

    print(f"\n✓ Report generated from {filename}")


if __name__ == '__main__':
    main()
