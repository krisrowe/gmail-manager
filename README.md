# Personal Gmail Manager

A Python-based Gmail management tool that automatically organizes, labels, and archives emails based on configurable rules.

## Features

- **Rule-based email processing**: Define rules in YAML to automatically manage emails
- **Label management**: Apply custom labels to emails
- **Importance marking**: Mark emails as important (high priority)
- **Email archiving**: Automatically archive emails based on age
- **Statistics reporting**: Get detailed statistics on processed emails
- **Inbox filtering**: All rules operate on Inbox emails by default

## Installation

### Prerequisites

1. **Python 3.9+**
2. **gworkspace-access CLI**: The `gwsa` command-line tool must be installed and configured

### Installing gworkspace-access

If you haven't already installed `gwsa`, follow the setup in the [gworkspace-access repository](https://github.com/krisrowe/gworkspace-access):

```bash
# Clone the gworkspace-access repo
git clone https://github.com/krisrowe/gworkspace-access.git
cd gworkspace-access

# Install gwsa in development mode
pip install -e .

# Run the initial setup (required first time)
gwsa setup
```

### Installing gmail-manager

```bash
# Clone this repository
git clone https://github.com/krisrowe/gmail-manager.git
cd gmail-manager

# Install Python dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x gmail_manager.py
```

## Configuration

Edit `config.yaml` to define your email management rules. Each rule has the following options:

```yaml
rules:
  - name: "Rule Name"                    # Display name for reporting
    filter: 'from:sender@example.com'   # Gmail search filter
    label: MyLabel                       # (optional) Label to apply
    mark_important: false                # (optional) Mark as important (Bills typically uses true)
    inbox_days: 30                       # Days before archiving; 0 = immediately archive
```

### Rule Fields

- **name** (required): A descriptive name for the rule (used in reporting)
- **filter** (required): A Gmail search query (see Gmail Search Syntax below)
- **label** (optional): Label to apply to matching emails (null = no label)
- **mark_important** (optional): Set to `true` to mark matching emails as important (default: false)
- **inbox_days** (optional): Days to keep in Inbox before archiving. Use `0` to immediately archive (default: 0)

### Gmail Search Syntax Examples

```
from:sender@example.com                           # Emails from specific sender
subject:"specific subject"                        # Emails with exact subject match
label:SomeLabel                                   # Emails with specific label
from:domain.org -from:person@domain.org          # Include/exclude patterns
(subject:"Option 1" OR subject:"Option 2")       # Boolean OR
"Exact phrase in email"                          # Search for exact phrase
after:2025-11-27                                 # Emails after specific date
```

For comprehensive Gmail search options, see [Gmail Search Help](https://support.google.com/mail/answer/7190)

## Usage

### Running the Manager

Run the gmail manager:

```bash
python gmail_manager.py
```

Or make it executable and run directly:

```bash
./gmail_manager.py
```

### Processing Flow

The tool executes the following workflow:

1. **Check gwsa installation** - Verifies the `gwsa` CLI is installed and available
2. **Load configuration** - Reads rules from `config.yaml`
3. **Fetch existing important emails** - Queries Gmail once for all currently important emails in Inbox (for protection from archival)
4. **Process importance-marking rules first** - Rules with `mark_important: true` run first and expand the protected set
5. **Process other rules** - Regular rules run, protected emails are never archived
6. **Generate reports** - Displays summary statistics and creates detailed JSON report

### Output Files

After each run, the tool generates:

- **Console output**: Statistics table showing emails found, labeled, marked important, and archived per rule
- **`processed_YYYY-MM-DD_HHMM.json`**: Detailed record of every email processed, including:
  - Email ID, subject, sender, date
  - Which rule matched
  - Actions taken (marked_important, archived, will_archive_later, won't_archive, none)
  - Label information

The JSON file is timestamped with the start time of the run and is useful for auditing and verification.

### Example Console Output

```
Processing 10 rules...
Note: Rules that mark emails as important are executed first.

Fetching existing important emails from Inbox... found 8

Processing 2 rule(s) that mark emails as important...
Processing rule: Bills... found 5 emails, marked 5 as important
Processing rule: Medical Results... found 1 emails, marked 1 as important

Processing 8 other rule(s)...
Processing rule: Newsletter... found 3 emails
Processing rule: Daily Digest... found 2 emails
...

====================================================================================================
Gmail Manager - Processing Results
====================================================================================================
Rule Name                           Found    Labeled  Important  Archived
----------------------------------------------------------------------------------------------------
Bills                               5        5        5          0
Medical Results                     1        0        1          0
Newsletter                          3        3        0          2
Daily Digest                        2        0        0          2
Service Alerts                      1        0        0          1
----------------------------------------------------------------------------------------------------
TOTAL                               12       8        6          5
====================================================================================================

📌 Protected 14 email(s) marked as important from archival.

Detailed results saved to: processed_2025-11-28_1925.json
```

### Important Email Protection

Emails marked as important by any rule are **never automatically archived**, regardless of their age. This protection works across:

- **This run**: Emails marked important by one rule are protected from archival by subsequent rules
- **Previous runs**: Emails marked important in earlier runs are queried once at startup and protected

To verify archival decisions, check the generated JSON file's `archive_action` field for each email.

## Example Rules

See `config.example.yaml` for example rule configurations. Common rule patterns include:

### Important-marking rules (always run first)
- **Bills**: Apply "Bills" label and mark important, archive after 30 days
- **Medical Results**: Mark important, never auto-archive (inbox_days: -1)

### Immediate archive rules (inbox_days: 0)
- **Small Recurring Charges**: Low-value receipts, labeled "Skipped"
- **Policy Updates**: Terms of service and privacy policy emails
- **Feedback Requests**: Survey and feedback request emails

### Time-delayed archive rules
- **Newsletters**: Organization emails with exclusions for important topics
- **Daily Digests**: Notification digests, archive after 3 days
- **Service Alerts**: Provider notifications, archive after 2 days
- **Archivable**: Any email with "Archivable" label, archive after 7 days

## Verification and Auditing

### JSON Report Format

The `processed_YYYY-MM-DD_HHMM.json` file contains detailed records for verification:

```json
{
  "started_at": "2025-11-28T19:25:00.123456",
  "completed_at": "2025-11-28T19:25:45.654321",
  "total_emails_processed": 25,
  "emails": [
    {
      "email_id": "19acd10a54b53779",
      "rule_name": "Bills",
      "subject": "Your bill is due",
      "sender": "Billing <billing@example.com>",
      "date": "Sat, 29 Nov 2025 00:43:29 +0000 (UTC)",
      "labeled": true,
      "action": "marked_important"
    },
    {
      "email_id": "19accb2cea94b015",
      "rule_name": "Newsletter",
      "subject": "Weekly Newsletter",
      "sender": "News <news@example.org>",
      "date": "Fri, 28 Nov 2025 23:01:00 +0000",
      "labeled": false,
      "action": "will_archive_later"
    }
  ]
}
```

### Action Field Values

- **marked_important**: Email was marked with the IMPORTANT flag (never archived)
- **archived**: Email was successfully archived (INBOX label removed)
- **will_archive_later**: Email is not old enough yet, will be archived when inbox_days threshold is reached
- **won't_archive**: Email is marked important and will never be archived
- **none**: Email matched rule but no archival action applies
- **failed**: Attempted action failed (check logs for details)

### Verification Steps

1. Run the manager and note the output filename
2. Review the JSON file to see all processed emails
3. For each email you want to verify:
   - Note the `email_id`
   - Check `action` to see what should have happened
   - Verify in Gmail that the action was taken correctly
4. If discrepancies are found, check:
   - Email filter matches rule criteria
   - Gmail API permissions are correct
   - Archived emails are in "All Mail" with INBOX label removed

## GCP Project

This project uses a GCP project labeled `gws-access:default`. To find the project ID:

```bash
PROJECT_ID=$(gcloud projects list --filter="labels.gws-access=default" --format="value(projectId)")
echo $PROJECT_ID
```

Use this project ID for all gcloud and terraform commands below.

## Storing OAuth2 Client Credentials

After creating OAuth2 credentials in GCP Console and downloading `client_secrets.json`, store a backup in Secrets Manager:

```bash
gcloud secrets create gmail-manager-client-secrets \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

gcloud secrets versions add gmail-manager-client-secrets \
  --data-file=~/.config/gworkspace-access/client_secrets.json \
  --project=$PROJECT_ID
```

**Why?** Once downloaded from GCP Console, this file cannot be retrieved again. If lost, you must create new credentials. This is simply a safe storage location - nothing accesses it programmatically at build time or runtime. It's only needed manually to run `gwsa setup` if re-authentication is required (locally or in the cloud).

## Cloud Run Deployment

See [terraform/README.md](terraform/README.md).

## Development

### Running Pre-commit Checks

Before committing, always run [devws](https://github.com/krisrowe/ws-sync) precommit:

```bash
devws precommit
```

This ensures code quality and catches potential issues before they're committed.

### Git Workflow

```bash
# Make your changes
vim config.yaml

# Run pre-commit checks
devws precommit

# Commit your changes
git add .
git commit -m "Update email rules for new senders"

# Push to remote
git push
```

## Troubleshooting

### "gwsa command not found"

Ensure `gwsa` is installed and in your PATH:
```bash
which gwsa
```

If not found, follow the [gworkspace-access installation](#installing-gworkspace-access) steps.

### "credentials file not found"

Make sure you've run `gwsa setup` in the gworkspace-access directory:
```bash
cd /path/to/gworkspace-access
gwsa setup
```

### Gmail API errors

Check that you have proper Gmail API permissions:
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Ensure the Gmail API is enabled for your project
3. Check that your OAuth credentials have the necessary scopes

## Future Enhancements

### Token Refresh Resilience

OAuth token is uploaded to Secrets Manager only at job end. If the job crashes after token refresh but before upload, the refreshed token is lost. This is generally self-healing because the refresh_token (long-lived) rarely changes - only the access_token (1 hour) is lost, and the next run will refresh again.

Potential improvement: upload token immediately after refresh via signal handler or gwsa hook.

### Git History Audit

Before making this repository public, audit the git history to ensure no sensitive data (personal names, vendor names, project IDs, etc.) remains from historical commits. Use tools like `git filter-repo` or BFG Repo-Cleaner to scrub history if needed.

### Gemini-Powered Calendar Event Extraction

Add rule-level configuration to scan emails for calendar events using the Gemini API. When enabled on a rule, matching emails would be analyzed to extract events (dates, times, locations, descriptions) and automatically create calendar entries via `gwsa calendar` commands (yet to be built).

Example use case: Emails from a school district could be scanned for events like parent-teacher conferences, school closures, or activity dates, and those would be added to Google Calendar automatically.

Proposed rule configuration:
```yaml
rules:
  - name: "School District Events"
    filter: 'from:@myschooldistrict.org'
    label: School
    extract_calendar_events: true  # Enable Gemini-based event extraction
```

This feature would require:
- Integration with the Gemini API for natural language event extraction
- New `gwsa calendar create` command for adding calendar entries
- Event deduplication to avoid creating duplicate entries on re-runs

## Configuration Management

The `config.yaml` file contains sensitive information and is not bundled in the Docker image. It is stored in Secrets Manager and downloaded at runtime.

### Secrets Manager

The following secrets are used in Cloud Run:

| Secret ID | Description | Managed By |
|-----------|-------------|------------|
| `gmail-manager-user-token` | OAuth token (user_token.json) | Runtime (refreshed by job) |
| `gmail-manager-config` | Email rules (config.yaml) | Terraform (synced on apply) |

The token secret is updated by the Cloud Run job when OAuth tokens are refreshed. The config secret is managed by Terraform - local `config.yaml` changes are synced to Secrets Manager on `terraform apply`.

### Local Development

For local development, `config.yaml` must exist in the project root. Options to create it:

```bash
# Option 1: Copy from example and customize
cp config.example.yaml config.yaml

# Option 2: Download from Secrets Manager (if already deployed)
gcloud secrets versions access latest --secret=gmail-manager-config --project=$PROJECT_ID > config.yaml

# Option 3: Restore from devws secrets
devws secrets get gmail-manager-config --output-file config.yaml
```

Use `devws secrets` to backup/restore your config via Google Cloud Secret Manager:

```bash
# Backup config to Secret Manager
devws secrets put gmail-manager-config --file config.yaml

# Restore config from Secret Manager
devws secrets get gmail-manager-config --output-file config.yaml
```

The `config.yaml` file is gitignored. If it was previously committed, remove it from git history before the gitignore takes effect:

```bash
git filter-repo --path config.yaml --invert-paths --force
git push origin --force --all
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[License details here]
