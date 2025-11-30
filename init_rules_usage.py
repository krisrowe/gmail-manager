#!/usr/bin/env python3
"""
Initialize rules_usage.json from processed_*.json files.
Extracts the most recent email date for each rule across all processed runs.
"""

import json
from pathlib import Path
from datetime import datetime

def parse_email_date(date_str: str) -> datetime:
    """Parse email date string to datetime for comparison"""
    # Remove timezone info for simplicity
    date_str = date_str.split(' +')[0].split(' -')[0].strip()
    try:
        return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S')
    except ValueError:
        return datetime.min

def main():
    """Extract most recent email dates from all processed files"""
    base_path = Path(__file__).parent
    rules_usage = {}

    # Find all processed_*.json files
    processed_files = sorted(base_path.glob('processed_*.json'))

    if not processed_files:
        print("No processed_*.json files found")
        return

    print(f"Found {len(processed_files)} processed file(s)")

    # Process each file
    for processed_file in processed_files:
        print(f"Processing {processed_file.name}...")

        with open(processed_file, 'r') as f:
            data = json.load(f)

        # Extract emails
        emails = data.get('emails', [])

        for email in emails:
            rule_name = email.get('rule_name')
            email_date = email.get('date')

            if not rule_name or not email_date:
                continue

            # Update if this is newer than what we have
            if rule_name not in rules_usage:
                rules_usage[rule_name] = email_date
            else:
                # Compare dates
                current_date = parse_email_date(rules_usage[rule_name])
                new_date = parse_email_date(email_date)
                if new_date > current_date:
                    rules_usage[rule_name] = email_date

    # Sort by rule name for readability
    rules_usage_sorted = {k: rules_usage[k] for k in sorted(rules_usage.keys())}

    # Write to rules_usage.json
    output_path = base_path / 'rules_usage.json'
    with open(output_path, 'w') as f:
        json.dump(rules_usage_sorted, f, indent=2)

    print(f"\nInitialized rules_usage.json with {len(rules_usage_sorted)} rule(s)")

    # Print summary
    for rule_name, date in rules_usage_sorted.items():
        print(f"  {rule_name}: {date}")

if __name__ == '__main__':
    main()
