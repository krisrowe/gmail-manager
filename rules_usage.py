#!/usr/bin/env python3
"""
Shared rules usage tracking utilities.
Manages reading and writing rules_usage.json to track most recent email dates per rule.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict
from app_config import GMAIL_MANAGER_DATA_DIR

def parse_email_date_to_iso(email_date_str: str) -> str:
    """Convert Gmail date format to ISO 8601 format for reliable storage.
    Preserves the original date/time values and timezone offset."""
    try:
        # Parse email date (Gmail format: "Fri, 28 Nov 2025 13:29:02 +0000" or "-0700")
        # Extract timezone offset
        if ' +' in email_date_str:
            date_part, tz_part = email_date_str.rsplit(' +', 1)
            tz_offset = '+' + tz_part.split()[0]  # Extract just the offset
        elif ' -' in email_date_str:
            # Need to find the last occurrence to avoid splitting on negative numbers
            parts = email_date_str.rsplit(' -', 1)
            date_part = parts[0]
            tz_offset = '-' + parts[1].split()[0]  # Extract just the offset
        else:
            tz_offset = '+00:00'  # Default to UTC if no timezone found
            date_part = email_date_str

        # Parse the date part
        date_part = date_part.strip()
        email_date = datetime.strptime(date_part, '%a, %d %b %Y %H:%M:%S')

        # Format timezone offset to ISO 8601 format (HH:MM)
        # Convert "0000" or "0700" to "00:00" or "07:00"
        tz_str = tz_offset.replace(' ', '')
        if len(tz_str) == 5:  # e.g., "+0000" or "-0700"
            tz_formatted = tz_str[:3] + ':' + tz_str[3:]  # "+00:00" or "-07:00"
        else:
            tz_formatted = tz_str

        return email_date.isoformat() + tz_formatted
    except Exception:
        return email_date_str  # Return original if parsing fails

def load_rules_usage(rules_usage_path: str) -> Dict[str, str]:
    """Load existing rules_usage.json or return empty dict"""
    try:
        if Path(rules_usage_path).exists():
            with open(rules_usage_path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_rules_usage(rules_usage: Dict[str, str], rules_usage_path: str) -> None:
    """Save rules_usage.json"""
    try:
        # Sort by rule name for readability
        rules_usage_sorted = {k: rules_usage[k] for k in sorted(rules_usage.keys())}
        with open(rules_usage_path, 'w') as f:
            json.dump(rules_usage_sorted, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save rules_usage.json: {e}")

def update_rules_usage_from_processed_file(processed_file_path: str, rules_usage_path: str) -> int:
    """
    Update rules_usage.json from a processed JSON file.
    Returns the number of updates made.
    """
    if not Path(processed_file_path).exists():
        print(f"Error: File '{processed_file_path}' not found")
        return 0

    # Load the processed file
    with open(processed_file_path, 'r') as f:
        data = json.load(f)

    # Load existing rules_usage
    rules_usage = load_rules_usage(rules_usage_path)

    # Extract emails and update rules_usage
    emails = data.get('emails', [])
    updates_made = 0

    for email in emails:
        rule_name = email.get('rule_name')
        email_date = email.get('date')

        if not rule_name or not email_date:
            continue

        # Convert to ISO format for reliable comparison and storage
        iso_date = parse_email_date_to_iso(email_date)

        # Update if this is newer than what we have
        if rule_name not in rules_usage:
            rules_usage[rule_name] = iso_date
            updates_made += 1
        else:
            # Compare dates as strings (ISO format is lexicographically sortable)
            if iso_date > rules_usage[rule_name]:
                rules_usage[rule_name] = iso_date
                updates_made += 1

    # Save updated rules_usage.json
    save_rules_usage(rules_usage, rules_usage_path)

    return updates_made

def main():
    """CLI entry point for updating rules_usage.json from processed files"""
    if len(sys.argv) < 2:
        print("Usage: python rules_usage.py <processed_json_file>")
        print("\nExample:")
        print("  python rules_usage.py processed_2025-11-28_1948.json")
        sys.exit(1)

    filename = sys.argv[1]
    data_dir = Path(GMAIL_MANAGER_DATA_DIR)
    processed_file = data_dir / filename
    rules_usage_path = data_dir / 'rules_usage.json'

    print(f"Processing {filename}...")

    updates_made = update_rules_usage_from_processed_file(str(processed_file), str(rules_usage_path))

    # Load and display updated rules_usage
    rules_usage = load_rules_usage(str(rules_usage_path))

    print(f"\nUpdated rules_usage.json with {updates_made} update(s)")
    print(f"Total rules tracked: {len(rules_usage)}\n")

    # Print summary
    for rule_name, date in sorted(rules_usage.items()):
        print(f"  {rule_name}: {date}")

if __name__ == '__main__':
    main()
