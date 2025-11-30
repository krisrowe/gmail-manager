#!/usr/bin/env python3
"""
Pagination Fetcher - Fetches emails from Gmail API with pagination support
Processes all Inbox emails in pages for client-side rule matching
"""

import subprocess
import json
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PaginationFetcher:
    """Fetches emails from a specified label using pagination"""

    def __init__(self, max_results: int = 20, required_label: str = "INBOX"):
        """
        Initialize fetcher

        Args:
            max_results: Maximum number of emails to fetch per page (default 20, Gmail API default is 10, max is 500)
            required_label: Label to fetch emails from (default INBOX, use Test for integration tests)
        """
        self.max_results = max_results
        self.required_label = required_label

    def fetch_all_inbox_emails(self, max_count: int = None, process_all: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch emails from Inbox with pagination support.

        Args:
            max_count: Maximum number of emails to fetch. If None, fetch only first page.
                      If set, fetches pages until reaching max_count or running out of pages.
            process_all: If True, fetch all pages. If False, respect max_count limit.

        Returns:
            Tuple of (list of emails, metadata dict with page info)
        """
        all_emails = []
        metadata = {
            'total_estimated': 0,
            'pages_processed': 0,
            'emails_fetched': 0,
            'more_available': False
        }

        page_num = 1
        next_page_token = None

        while True:
            logger.info(f"Fetching page {page_num} (page size: {self.max_results})")
            emails, page_meta = self._fetch_page(next_page_token)

            if page_num == 1:
                # Set total estimate from first page
                metadata['total_estimated'] = page_meta.get('resultSizeEstimate', 0)

            all_emails.extend(emails)
            metadata['pages_processed'] = page_num
            metadata['emails_fetched'] = len(all_emails)
            logger.info(f"Page {page_num} complete: fetched {len(emails)} emails, total so far: {len(all_emails)}")

            # Check if more pages available
            next_page_token = page_meta.get('nextPageToken')
            metadata['more_available'] = bool(next_page_token)

            # Determine if we should stop fetching
            should_stop = False
            if not next_page_token:
                # No more pages available
                should_stop = True
            elif process_all:
                # Continue fetching all pages
                should_stop = False
            elif max_count is None:
                # Fetch only first page if max_count not specified
                should_stop = True
            elif len(all_emails) >= max_count:
                # Stop when we've fetched enough emails
                should_stop = True

            if should_stop:
                break

            page_num += 1

        return all_emails, metadata

    def _fetch_page(self, page_token: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch a single page of emails from Inbox

        Args:
            page_token: Token for pagination, None for first page

        Returns:
            Tuple of (list of emails on this page, response metadata)
        """
        # Build gwsa command with pagination support
        cmd = ['gwsa', 'mail', 'search', f'label:{self.required_label}', '--max-results', str(self.max_results), '--format', 'full']

        if page_token:
            cmd.extend(['--page-token', page_token])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )

            if not result.stdout.strip():
                return [], {'resultSizeEstimate': 0, 'nextPageToken': None}

            emails = json.loads(result.stdout)
            if not isinstance(emails, list):
                return [], {'resultSizeEstimate': 0, 'nextPageToken': None}

            # Extract pagination info from stderr logs (gwsa logs pagination info)
            metadata = self._parse_metadata_from_stderr(result.stderr)

            return emails, metadata

        except subprocess.CalledProcessError as e:
            print(f"Error fetching emails: {e.stderr}")
            return [], {'resultSizeEstimate': 0, 'nextPageToken': None}
        except json.JSONDecodeError as e:
            print(f"Error parsing email results: {e}")
            return [], {'resultSizeEstimate': 0, 'nextPageToken': None}
        except subprocess.TimeoutExpired:
            print("Error: Email fetch timeout")
            return [], {'resultSizeEstimate': 0, 'nextPageToken': None}

    def _parse_metadata_from_stderr(self, stderr: str) -> Dict[str, Any]:
        """
        Parse pagination metadata from gwsa stderr logs

        gwsa logs pagination info like:
        "Found X messages (estimated total: Y)"
        "More pages available. Use --page-token ABC123 to fetch next page"

        Args:
            stderr: stderr output from gwsa command

        Returns:
            Dict with resultSizeEstimate and nextPageToken
        """
        metadata = {
            'resultSizeEstimate': 0,
            'nextPageToken': None
        }

        if not stderr:
            return metadata

        # Look for pagination info in stderr logs
        for line in stderr.split('\n'):
            # Extract resultSizeEstimate from "estimated total: X"
            if 'estimated total:' in line.lower():
                try:
                    # Extract number after "estimated total:"
                    parts = line.split('estimated total:')
                    if len(parts) > 1:
                        num_str = parts[1].strip().split()[0].rstrip(')')
                        metadata['resultSizeEstimate'] = int(num_str)
                except (ValueError, IndexError):
                    pass

            # Extract nextPageToken from "Use --page-token ABC123"
            if '--page-token' in line:
                try:
                    # Extract token after "--page-token"
                    parts = line.split('--page-token')
                    if len(parts) > 1:
                        token = parts[1].strip().split()[0]
                        metadata['nextPageToken'] = token
                except IndexError:
                    pass

        return metadata

    def fetch_with_gmail_api(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch emails directly using Gmail API for proper pagination support

        This requires direct access to Gmail API client, which is available
        in gwsa_cli but we need to refactor to access it directly.

        Returns:
            Tuple of (list of emails, metadata)
        """
        # TODO: Implement direct Gmail API access for pagination
        # This would require importing from gwsa_cli.mail module
        # and calling the Gmail service directly
        raise NotImplementedError(
            "Direct Gmail API pagination not yet implemented. "
            "Currently using gwsa CLI which doesn't support pagination."
        )
