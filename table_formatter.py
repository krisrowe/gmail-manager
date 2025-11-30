#!/usr/bin/env python3
"""
Shared table formatting utilities for gmail-manager and report.py
"""

from typing import List, Any


def format_rule_summary_table(rules_data: List[Any], totals: dict = None, title: str = "Rule Summary") -> str:
    """
    Format a rule summary table.

    Args:
        rules_data: List of rule statistics (dict with keys: name, emails_found, emails_processed, emails_labeled, emails_marked_important, emails_archived)
        totals: Optional dict with keys matching rule fields for total row
        title: Title to display in the table header

    Returns:
        Formatted table as string
    """
    lines = []
    lines.append("\n" + "=" * 110)
    lines.append(title)
    lines.append("=" * 110)
    lines.append(f"{'Rule Name':<40} {'Found':<8} {'Processed':<10} {'Labeled':<8} {'Important':<10} {'Archived':<10}")
    lines.append("-" * 110)

    for rule in rules_data:
        rule_name = rule['name'][:39] if len(rule['name']) > 39 else rule['name']
        lines.append(
            f"{rule_name:<40} {rule['emails_found']:<8} {rule['emails_processed']:<10} "
            f"{rule['emails_labeled']:<8} {rule['emails_marked_important']:<10} {rule['emails_archived']:<10}"
        )

    lines.append("-" * 110)

    if totals:
        lines.append(
            f"{'TOTAL':<40} {totals.get('emails_found', 0):<8} {totals.get('emails_processed', 0):<10} "
            f"{totals.get('emails_labeled', 0):<8} {totals.get('emails_marked_important', 0):<10} {totals.get('emails_archived', 0):<10}"
        )

    lines.append("=" * 110)

    return "\n".join(lines)


def format_email_details_table(emails: List[dict]) -> str:
    """
    Format an email details table.

    Args:
        emails: List of email records with keys: email_id, rule_name, subject, action, labeled

    Returns:
        Formatted table as string
    """
    lines = []
    lines.append("\n" + "=" * 140)
    lines.append("Processed Emails Details")
    lines.append("=" * 140)

    if not emails:
        lines.append("No emails were processed.")
        lines.append("=" * 140)
        return "\n".join(lines)

    lines.append(f"{'Email ID':<20} {'Rule':<35} {'Subject':<40} {'Action':<20} {'Labeled':<10}")
    lines.append("-" * 140)

    for email in emails:
        email_id = email['email_id'][:19]
        rule = email['rule_name'][:34] if len(email['rule_name']) > 34 else email['rule_name']
        subject = email['subject'][:39] if len(email['subject']) > 39 else email['subject']
        action = email['action'][:19]
        labeled = "Yes" if email['labeled'] else "No"

        lines.append(f"{email_id:<20} {rule:<35} {subject:<40} {action:<20} {labeled:<10}")

    lines.append("=" * 140)

    return "\n".join(lines)
