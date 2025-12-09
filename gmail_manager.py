#!/usr/bin/env python3
"""
Gmail Manager - Process and organize emails based on configured rules

Uses pagination-based fetching with client-side regex matching.
Rules that mark emails as important are always executed first.
"""

import json
import subprocess
import sys
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
import yaml
from typing import Dict, List, Any, Set
from dataclasses import dataclass, field, asdict
from rules_usage import load_rules_usage, save_rules_usage
import report as report_module
from rule_matcher import RuleMatcher
from pagination_fetcher import PaginationFetcher
from app_config import GMAIL_MANAGER_CONFIG_DIR, GMAIL_MANAGER_DATA_DIR

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ProcessedEmail:
    """Record of a processed email"""
    email_id: str
    rule_name: str
    subject: str
    sender: str
    date: str
    labeled: bool = False
    action: str = "none"  # "marked_important", "archived", "will_archive_later", "won't_archive", "none"


@dataclass
class RuleStats:
    """Statistics for a single rule"""
    name: str
    filter: str
    emails_found: int = 0
    emails_processed: int = 0  # Total emails actually updated (labeled, marked important, or archived)
    emails_labeled: int = 0
    emails_marked_important: int = 0
    emails_archived: int = 0
    errors: List[str] = field(default_factory=list)


def check_gwsa_installed() -> bool:
    """Check if gwsa CLI is installed"""
    try:
        result = subprocess.run(['which', 'gwsa'], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except Exception:
        pass
    return False


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        sys.exit(1)




def search_emails(filter_query: str, required_label: str = "INBOX") -> List[Dict[str, str]]:
    """Search for emails matching the given filter"""
    try:
        # Build the full search query - always filter to required label first
        full_query = f'label:{required_label} {filter_query}'

        result = subprocess.run(
            ['gwsa', 'mail', 'search', full_query],
            capture_output=True,
            text=True,
            check=True
        )

        if not result.stdout.strip():
            return []

        # Parse JSON output from stdout only (gwsa logs go to stderr)
        emails = json.loads(result.stdout)
        return emails if isinstance(emails, list) else []

    except subprocess.CalledProcessError as e:
        print(f"Error searching emails: {e.stderr}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing search results JSON: {e}")
        print(f"Got stdout: {result.stdout[:200]}")
        return []


def add_label(email_id: str, label: str) -> bool:
    """Add a label to an email"""
    try:
        result = subprocess.run(
            ['gwsa', 'mail', 'label', email_id, label],
            capture_output=True,
            text=True,
            check=True
        )
        # Just check for success - gwsa outputs JSON but we only care about success
        if result.returncode == 0:
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error adding label to {email_id}: {e.stderr}")
        return False


def mark_important(email_id: str) -> bool:
    """Mark an email as important"""
    try:
        # Gmail's IMPORTANT label is a built-in label
        result = subprocess.run(
            ['gwsa', 'mail', 'label', email_id, 'IMPORTANT'],
            capture_output=True,
            text=True,
            check=True
        )
        # Just check for success
        if result.returncode == 0:
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error marking {email_id} as important: {e.stderr}")
        return False


def archive_email(email_id: str, required_label: str = "INBOX", final_archive_label: str = "Archive Complete") -> bool:
    """Archive an email (remove required_label) and apply final archive label"""
    try:
        # First, remove the INBOX label
        result = subprocess.run(
            ['gwsa', 'mail', 'label', email_id, required_label, '--remove'],
            capture_output=True,
            text=True,
            check=True
        )
        if result.returncode != 0:
            return False

        # Then, add the final archive label
        return add_label(email_id, final_archive_label)

    except subprocess.CalledProcessError as e:
        print(f"Error archiving {email_id}: {e.stderr}")
        return False


def get_important_emails_in_label(required_label: str = "INBOX") -> Set[str]:
    """
    Get all email IDs in the specified label that are marked as important.
    This is queried once upfront to avoid multiple API calls per email.
    """
    try:
        result = subprocess.run(
            ['gwsa', 'mail', 'search', f'label:{required_label} label:IMPORTANT'],
            capture_output=True,
            text=True,
            check=True
        )

        if not result.stdout.strip():
            return set()

        emails = json.loads(result.stdout)
        if not isinstance(emails, list):
            return set()

        # Extract IDs from the email list
        important_ids = {email.get('id') for email in emails if email.get('id')}
        return important_ids

    except Exception as e:
        print(f"Error fetching important emails from {required_label}: {e}")
        return set()


def parse_email_date_to_iso(email_date_str: str) -> str:
    """Convert Gmail date format to ISO 8601 format for reliable storage.
    Preserves the original date/time values and timezone offset."""
    try:
        # Extract timezone offset
        tz_offset = '+00:00'  # Default to UTC
        date_part = email_date_str

        # First remove timezone abbreviations in parentheses (e.g., "(CST)")
        date_part = re.sub(r'\s+\([A-Z]+\)$', '', date_part)

        # Extract timezone info
        if ' GMT' in date_part:
            parts = date_part.split(' GMT')
            date_part = parts[0]
            tz_offset = '+00:00'
        elif ' UTC' in date_part:
            parts = date_part.split(' UTC')
            date_part = parts[0]
            tz_offset = '+00:00'
        else:
            # Look for signed timezone offset at the end (+/-XXXX)
            match = re.search(r'\s+([+-]\d{4})', date_part)
            if match:
                tz_str = match.group(1)
                date_part = date_part[:match.start()].strip()
                tz_offset = tz_str[:3] + ':' + tz_str[3:]  # Format as +HH:MM or -HH:MM

        # Parse the date part
        date_part = date_part.strip()
        try:
            # Try standard format with day of week: "Fri, 28 Nov 2025 13:29:02"
            email_date = datetime.strptime(date_part, '%a, %d %b %Y %H:%M:%S')
        except ValueError:
            # Try format without day of week: "28 Nov 2025 13:29:02"
            email_date = datetime.strptime(date_part, '%d %b %Y %H:%M:%S')

        # Ensure tz_offset is properly formatted
        if ':' not in tz_offset:
            tz_str = tz_offset.replace(' ', '')
            if len(tz_str) == 5:  # e.g., "+0000" or "-0700"
                tz_offset = tz_str[:3] + ':' + tz_str[3:]  # "+00:00" or "-07:00"

        return email_date.isoformat() + tz_offset
    except Exception as e:
        logger.warning(f"Could not parse date '{email_date_str}': {e}")
        return email_date_str  # Return original if parsing fails


def should_archive(email_date_str: str, inbox_days: int) -> bool:
    """Check if an email should be archived based on age"""
    if inbox_days == 0:
        return True  # Immediately archive

    try:
        # Extract date part before timezone info (GMT, UTC, +XXXX, -XXXX, etc.)
        date_part = email_date_str

        # Remove timezone abbreviations in parentheses (e.g., "(CST)")
        date_part = re.sub(r'\s+\([A-Z]+\)$', '', date_part)

        # Remove timezone markers from the end
        for tz_marker in [' GMT', ' UTC']:
            if tz_marker in date_part:
                date_part = date_part.split(tz_marker)[0]

        # Handle signed offsets (+0000, -0700, etc.) - remove from end
        date_part = re.sub(r'\s+[+-]\d{4}$', '', date_part)

        date_part = date_part.strip()

        # Try standard format with day of week: "Fri, 28 Nov 2025 13:29:02"
        try:
            email_date = datetime.strptime(date_part, '%a, %d %b %Y %H:%M:%S')
        except ValueError:
            # Try format without day of week: "28 Nov 2025 13:29:02"
            email_date = datetime.strptime(date_part, '%d %b %Y %H:%M:%S')

        cutoff_date = datetime.now() - timedelta(days=inbox_days)
        return email_date < cutoff_date
    except Exception as e:
        logger.error(f"Error parsing date '{email_date_str}': {e}")
        return False




def parse_arguments():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Gmail Manager - Organize and archive emails based on configured rules'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of emails to process/update (label, mark important, archive). Default: 50.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run the script without making any changes. It will simulate actions and show what would be done.'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse command line arguments
    args = parse_arguments()
    limit = args.limit

    # Capture start time for output filename
    start_time = datetime.now()

    print(f"Processing limit: {limit} emails")
    print()

    # Check for gwsa installation
    if not check_gwsa_installed():
        print("Error: gwsa CLI is not installed or not in PATH")
        print("\nTo install gwsa, visit: https://github.com/krisrowe/gworkspace-access")
        print("Or if already installed, ensure it's in your PATH")
        sys.exit(1)

    # Load configuration (support GMAIL_MANAGER_CONFIG env var for integration tests)
    config_path = os.environ.get('GMAIL_MANAGER_CONFIG', str(Path(__file__).parent / 'config.yaml'))
    config = load_config(config_path)

    if 'rules' not in config:
        print("Error: No 'rules' found in configuration")
        sys.exit(1)

    # Get settings from config
    required_label = config.get('required_label', 'INBOX')
    auto_archive_label = config.get('auto_archive_label', 'Auto Archive')
    final_archive_label = config.get('final_archive_label', 'Archived')
    page_size = config.get('page_size', 20)
    
    # Determine limit with new hierarchy: CLI arg > config.yaml > hardcoded default
    if args.limit is not None:
        limit = args.limit
    else:
        limit = config.get('limit', 50)

    rules = config['rules']
    if not rules:
        print("Error: No rules defined in configuration")
        sys.exit(1)

    print(f"Loaded {len(rules)} rules from configuration")
    print()

    # Filter out disabled rules
    enabled_rules = [r for r in rules if r.get('enabled', True)]
    if len(enabled_rules) < len(rules):
        print(f"Note: {len(rules) - len(enabled_rules)} rule(s) disabled")

    # Fetch emails from specified label using pagination
    print(f"Fetching emails from {required_label}...", end=' ', flush=True)
    fetcher = PaginationFetcher(max_results=page_size, required_label=required_label)
    all_inbox_emails, fetch_metadata = fetcher.fetch_all_inbox_emails(max_count=limit)
    print(f"fetched {len(all_inbox_emails)} emails")
    print(f"  Estimated total in {required_label}: {fetch_metadata['total_estimated']}")
    if fetch_metadata['more_available']:
        print(f"  ⚠️  More pages available in Inbox - fetched up to limit of {limit}")
    print()

    # Initialize rule matcher
    matcher = RuleMatcher(case_insensitive=True)

    # Track all processed emails and statistics
    all_processed_emails: List[ProcessedEmail] = []
    all_stats = []
    remaining_limit = limit  # Track remaining emails we can process
    rules_usage_updates: Dict[str, str] = {}  # Track rule usage for rules_usage.json
    unmatched_emails = []  # Track emails that matched no rules
    failed_emails = []  # Track emails that failed during processing

    # Separate rules into two groups: those that mark important and those that don't
    important_rules = [r for r in enabled_rules if r.get('mark_important', False)]
    regular_rules = [r for r in enabled_rules if not r.get('mark_important', False)]

    print(f"Processing {len(enabled_rules)} enabled rules...")
    if important_rules:
        print(f"  {len(important_rules)} rule(s) mark emails as important")
    if regular_rules:
        print(f"  {len(regular_rules)} other rule(s)")
    print()

    # Create stats for all enabled rules
    stats_by_rule = {r.get('name', 'Unknown'): RuleStats(
        name=r.get('name', 'Unknown'),
        filter=r.get('filter', '')  # Keep for compatibility in output
    ) for r in enabled_rules}

    # Process each email against all rules
    emails_evaluated = 0  # Total emails we looped through
    actions_taken = 0     # Total number of actions taken (label, mark important, archive)

    for email_idx, email in enumerate(all_inbox_emails, 1):
        email_id = email.get('id')
        if not email_id:
            continue

        # Add sender field for RuleMatcher compatibility
        email['sender'] = email.get('from', '')

        # Check if we've hit the global limit on emails to evaluate
        if remaining_limit is not None and emails_evaluated >= remaining_limit:
            break

        emails_evaluated += 1

        # Collect all matching rules and decisions for this email
        matching_rules = []
        labels_to_apply = set()
        should_mark_important_final = False
        inbox_days_values = []  # Collect all specified inbox_days values

        # Check all rules (both important and regular)
        for rule in enabled_rules:
            if matcher.matches_rule(email, rule):
                rule_name = rule.get('name', 'Unknown')
                matching_rules.append(rule)
                stat = stats_by_rule[rule_name]
                stat.emails_found += 1

                # Collect labels to apply
                label = rule.get('label')
                if label:
                    labels_to_apply.add(label)

                # Track if any rule marks important
                if rule.get('mark_important', False):
                    should_mark_important_final = True

                # Collect inbox_days values
                inbox_days = rule.get('inbox_days')
                if inbox_days is not None:
                    inbox_days_values.append(inbox_days)
                    # Automatically apply auto_archive_label for rules with positive inbox_days
                    if inbox_days > 0:
                        labels_to_apply.add(auto_archive_label)

        # If no rules matched, add to unmatched list
        if not matching_rules:
            unmatched_emails.append(email_id)
            continue

        # Determine final archive action based on all matching rules
        # If any rule has inbox_days=-1, never archive
        # Otherwise, use maximum inbox_days (most conservative)
        final_inbox_days = None
        if -1 in inbox_days_values:
            final_inbox_days = -1
            logger.debug(f"Email {email_id}: Rule with inbox_days=-1 found, will never archive")
        elif inbox_days_values:
            final_inbox_days = max(inbox_days_values)
            logger.debug(f"Email {email_id}: Multiple rules have inbox_days={inbox_days_values}, using max={final_inbox_days}")
        else:
            logger.debug(f"Email {email_id}: No matching rule specifies inbox_days, no archiving action")
        # If no inbox_days specified by any matching rule, final_inbox_days stays None

        # Now execute actions for each matching rule
        email_had_action = False  # Track if this email had any actions taken
        for rule in matching_rules:
            rule_name = rule.get('name', 'Unknown')
            stat = stats_by_rule[rule_name]
            action = "none"

            # Mark as important if needed
            if rule.get('mark_important', False):
                if mark_important(email_id):
                    stat.emails_marked_important += 1
                    actions_taken += 1
                    email_had_action = True
                action = "marked_important"

            # Add labels if needed
            label = rule.get('label')
            if label and label in labels_to_apply:
                if add_label(email_id, label):
                    stat.emails_labeled += 1
                    actions_taken += 1
                    email_had_action = True
                labels_to_apply.discard(label)  # Mark as applied

            # Handle archiving based on final_inbox_days
            if final_inbox_days is None:
                # No archiving decision from any rule
                if action == "none":
                    logger.debug(f"Email {email_id} (rule: {rule_name}): No archiving decision, action=none")
                    action = "none"
            elif final_inbox_days == -1:
                # Never archive
                logger.debug(f"Email {email_id} (rule: {rule_name}): final_inbox_days=-1, won't archive")
                action = "won't_archive"
            elif final_inbox_days == 0:
                # Archive immediately
                logger.debug(f"Email {email_id} (rule: {rule_name}): final_inbox_days=0, checking should_archive(0)")
                if should_archive(email.get('date', ''), 0):
                    logger.debug(f"Email {email_id}: should_archive=True, attempting to archive")
                    if archive_email(email_id, required_label, final_archive_label):
                        stat.emails_archived += 1
                        action = "archived"
                        actions_taken += 1
                        email_had_action = True
                        logger.debug(f"Email {email_id}: Successfully archived")
                    else:
                        action = "failed"
                        logger.error(f"Email {email_id}: Failed to archive (rule: {rule_name})")
                        failed_emails.append({
                            'email_id': email_id,
                            'subject': email.get('subject', ''),
                            'error': 'Archive operation failed',
                            'rule': rule_name
                        })
                else:
                    logger.debug(f"Email {email_id}: should_archive=False for inbox_days=0")
            elif final_inbox_days > 0:
                # Archive after N days
                logger.debug(f"Email {email_id} (rule: {rule_name}): final_inbox_days={final_inbox_days}, checking should_archive({final_inbox_days})")
                if should_archive(email.get('date', ''), final_inbox_days):
                    logger.debug(f"Email {email_id}: should_archive=True, attempting to archive")
                    if archive_email(email_id, required_label, final_archive_label):
                        stat.emails_archived += 1
                        action = "archived"
                        actions_taken += 1
                        email_had_action = True
                        logger.debug(f"Email {email_id}: Successfully archived")
                    else:
                        action = "failed"
                        logger.error(f"Email {email_id}: Failed to archive (rule: {rule_name})")
                        failed_emails.append({
                            'email_id': email_id,
                            'subject': email.get('subject', ''),
                            'error': 'Archive operation failed',
                            'rule': rule_name
                        })
                else:
                    logger.debug(f"Email {email_id}: should_archive=False for inbox_days={final_inbox_days}, will_archive_later")
                    action = "will_archive_later"

            # Create processed email record
            processed_email = ProcessedEmail(
                email_id=email_id,
                rule_name=rule_name,
                subject=email.get('subject', ''),
                sender=email.get('sender', ''),
                date=email.get('date', ''),
                action=action
            )
            all_processed_emails.append(processed_email)
            rules_usage_updates[rule_name] = parse_email_date_to_iso(email.get('date', ''))

            # Increment emails_processed if this email had any actions
            if email_had_action:
                stat.emails_processed += 1
                email_had_action = False  # Reset for next rule

        # Apply any remaining labels in labels_to_apply (like Auto Archive label)
        if labels_to_apply:
            logger.debug(f"Email {email_id}: Applying {len(labels_to_apply)} remaining label(s): {labels_to_apply}")
            for remaining_label in labels_to_apply:
                if add_label(email_id, remaining_label):
                    actions_taken += 1
                    logger.debug(f"Email {email_id}: Successfully applied label '{remaining_label}'")
                else:
                    logger.debug(f"Email {email_id}: Failed to apply label '{remaining_label}'")

    # Build stats list for output
    all_stats = [stats_by_rule[rule.get('name', 'Unknown')] for rule in enabled_rules]

    # Write processed emails to timestamped JSON file
    output_filename = f"processed_{start_time.strftime('%Y-%m-%d_%H%M')}.json"
    output_path = Path(GMAIL_MANAGER_DATA_DIR) / output_filename

    # Build rule statistics for JSON
    rule_stats = []
    for stat in all_stats:
        rule_stats.append({
            "name": stat.name,
            "filter": stat.filter,
            "emails_found": stat.emails_found,
            "emails_processed": stat.emails_processed,
            "emails_labeled": stat.emails_labeled,
            "emails_marked_important": stat.emails_marked_important,
            "emails_archived": stat.emails_archived
        })

    emails_matched = len(all_inbox_emails) - len(unmatched_emails)

    processed_data = {
        "started_at": start_time.isoformat(),
        "completed_at": datetime.now().isoformat(),
        "limit": limit,
        "emails_evaluated": emails_evaluated,
        "emails_matched": emails_matched,
        "emails_unmatched": len(unmatched_emails),
        "total_rule_matches": sum(s.emails_found for s in all_stats),
        "total_actions_taken": sum(s.emails_processed for s in all_stats),
        "emails_fetched": len(all_inbox_emails),
        "more_pages_available": fetch_metadata['more_available'],
        "total_estimated_in_inbox": fetch_metadata['total_estimated'],
        "rule_statistics": rule_stats,
        "emails": [asdict(email) for email in all_processed_emails],
        "failed_emails": failed_emails
    }

    with open(output_path, 'w') as f:
        json.dump(processed_data, f, indent=2)

    # Display complete report
    report_module.generate_report(processed_data)
    print(f"\n✓ Report generated from {output_filename}")

    # Update rules_usage.json with most recent email dates
    if rules_usage_updates:
        rules_usage_path = Path(GMAIL_MANAGER_DATA_DIR) / 'rules_usage.json'
        rules_usage = load_rules_usage(str(rules_usage_path))
        rules_usage.update(rules_usage_updates)
        save_rules_usage(rules_usage, str(rules_usage_path))


if __name__ == '__main__':
    from cloud_secrets import CloudSecretsManager

    with CloudSecretsManager():
        main()
