#!/usr/bin/env python3
"""
Rule Matcher - Matches emails against configured rules using regex patterns
Supports pagination-based email processing with client-side pattern matching
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MatchCriteria:
    """Represents the positive match criteria for a rule"""
    sender: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    label_includes: Optional[str] = None
    to: Optional[str] = None


@dataclass
class ExcludeCriteria:
    """Represents the negative match criteria for a rule"""
    any: List[str] = None  # Matches in any field
    subject: List[str] = None  # Matches only in subject
    body: List[str] = None  # Matches only in body
    to: List[str] = None # Matches only in to

    def __post_init__(self):
        if self.any is None:
            self.any = []
        if self.subject is None:
            self.subject = []
        if self.body is None:
            self.body = []
        if self.to is None:
            self.to = []


class RuleMatcher:
    """Matches emails against rules using regex patterns"""

    def __init__(self, case_insensitive: bool = True):
        """
        Initialize matcher

        Args:
            case_insensitive: If True, all regex matching is case-insensitive
        """
        self.case_insensitive = case_insensitive
        self.regex_flags = re.IGNORECASE if case_insensitive else 0

    def matches_rule(self, email: Dict[str, Any], rule: Dict[str, Any]) -> bool:
        """
        Check if an email matches a rule

        Args:
            email: Email data with keys: id, subject, sender, body, labelIds, etc.
            rule: Rule config with match and exclude criteria

        Returns:
            True if email matches all positive criteria and none of the negative criteria
        """
        # Parse match criteria
        match_config = rule.get('match', {})
        match_criteria = MatchCriteria(
            sender=match_config.get('sender'),
            subject=match_config.get('subject'),
            body=match_config.get('body'),
            label_includes=match_config.get('label_includes'),
            to=match_config.get('to')
        )

        # Parse exclude criteria
        exclude_config = rule.get('exclude', {})
        exclude_criteria = ExcludeCriteria(
            any=exclude_config.get('any', []),
            subject=[exclude_config.get('subject')] if exclude_config.get('subject') else [],
            body=[exclude_config.get('body')] if exclude_config.get('body') else [],
            to=[exclude_config.get('to')] if exclude_config.get('to') else []
        )

        # Check positive criteria (all must match)
        if not self._matches_positive(email, match_criteria):
            return False

        # Check negative criteria (none must match)
        if self._matches_negative(email, exclude_criteria):
            return False

        return True

    def _matches_positive(self, email: Dict[str, Any], criteria: MatchCriteria) -> bool:
        """Check if email matches all positive criteria"""
        # If checking for a label, check labelIds
        if criteria.label_includes:
            label_ids = email.get('labelIds', [])
            if criteria.label_includes not in label_ids:
                return False

        # Check sender
        if criteria.sender:
            sender = email.get('sender', '')
            if not self._regex_search(criteria.sender, sender):
                return False

        # Check subject
        if criteria.subject:
            subject = email.get('subject', '')
            if not self._regex_search(criteria.subject, subject):
                return False

        # Check body
        if criteria.body:
            body = email.get('body', '') or email.get('snippet', '')
            if not self._regex_search(criteria.body, body):
                return False

        # Check to recipient
        if criteria.to:
            to_recipients = email.get('to', '')
            cc_recipients = email.get('cc', '')
            bcc_recipients = email.get('bcc', '')
            list_id = email.get('list_id', '')
            all_recipients = ' '.join(filter(None, [to_recipients, cc_recipients, bcc_recipients, list_id]))
            if not self._regex_search(criteria.to, all_recipients):
                return False

        return True

    def _matches_negative(self, email: Dict[str, Any], criteria: ExcludeCriteria) -> bool:
        """Check if email matches any negative criteria (should return True if it matches = excluded)"""
        sender = email.get('sender', '')
        subject = email.get('subject', '')
        body = email.get('body', '') or email.get('snippet', '')
        to_recipients = email.get('to', '')
        cc_recipients = email.get('cc', '')
        bcc_recipients = email.get('bcc', '')
        list_id = email.get('list_id', '')
        all_recipients = ' '.join(filter(None, [to_recipients, cc_recipients, bcc_recipients, list_id]))

        # Check any-field exclusions
        for pattern in criteria.any:
            if self._regex_search(pattern, sender) or \
               self._regex_search(pattern, subject) or \
               self._regex_search(pattern, body) or \
               self._regex_search(pattern, all_recipients):
                return True

        # Check subject exclusions
        for pattern in criteria.subject or []:
            if self._regex_search(pattern, subject):
                return True

        # Check body exclusions
        for pattern in criteria.body or []:
            if self._regex_search(pattern, body):
                return True

        # Check to exclusions
        for pattern in criteria.to or []:
            if self._regex_search(pattern, all_recipients):
                return True

        return False

    def _regex_search(self, pattern: str, text: str) -> bool:
        """
        Search for regex pattern in text

        Args:
            pattern: Regex pattern to search for
            text: Text to search in

        Returns:
            True if pattern matches anywhere in text
        """
        try:
            return bool(re.search(pattern, text, self.regex_flags))
        except re.error as e:
            print(f"Error compiling regex pattern '{pattern}': {e}")
            return False
