# Contributing to Personal Gmail Manager

## Development Workflow

### Running the Application

#### Default Run
```bash
python gmail_manager.py
```

Processes up to the first 20 emails from your Inbox (default limit) against all enabled rules.

#### Custom Limit
```bash
python gmail_manager.py --limit 50
```

Processes up to 50 emails from the first page. Useful for testing rule changes without affecting many emails.

#### Warning About Multiple Pages
The application processes one page at a time (25 emails per page by default). If your Inbox has more emails, the output will note:
```
⚠️  Limited to first page. More pages available - use --limit to control how many to process
```

This means there are additional emails beyond the first page that aren't being processed. To process more, increase the `--limit` value.

### Generating Reports

After running the application, a JSON file is created with the timestamp in your data directory:
```
~/.local/share/gmail-manager/processed_2025-11-29_1441.json
```

Generate a formatted report from any processed file:
```bash
# Using full path
python report.py ~/.local/share/gmail-manager/processed_2025-11-29_1441.json

# Or use find to locate a recent file
python report.py $(ls -t ~/.local/share/gmail-manager/processed_*.json | head -1)
```

This generates three sections:
1. **Processing Summary** - Overall timing and statistics
2. **Rule Summary** - Per-rule breakdown (emails found, processed, labeled, marked important, archived)
3. **Email Details** - Row-by-row details of each processed email

#### Regenerating Reports Without Gmail Impact

When working on reporting features or output format changes, you can regenerate reports from previously processed runs without modifying your Inbox:

```bash
# List all previous processed run files
ls -lh ~/.local/share/gmail-manager/processed_*.json

# Regenerate report from a previous run
python report.py ~/.local/share/gmail-manager/processed_2025-11-28_2020.json
```

This is useful for:
- Testing report formatting changes
- Iterating on table output without re-running email processing
- Auditing historical data
- Sharing analysis without re-processing

The `processed_*.json` files contain the complete email processing data, so the report generator can recreate the same analysis anytime. To quickly regenerate the latest report:

```bash
python report.py $(ls -t ~/.local/share/gmail-manager/processed_*.json | head -1)
```

### Working with Rules

Rules are defined in `config.yaml`. Each rule has:
- `name`: Rule identifier
- `enabled`: Toggle rule on/off (default: true)
- `filter`: Regex pattern to match emails
- `label`: Label to apply (optional)
- `mark_important`: Mark as important (boolean)
- `inbox_days`: Days to keep in Inbox before archiving (-1 = never archive, 0 = immediately archive, N = archive after N days)

### Testing Rule Changes

When modifying rules:

1. Make your changes to `config.yaml`
2. Run with `--limit` to test on a small sample:
   ```bash
   python gmail_manager.py --limit 3
   ```
3. Review the generated report:
   ```bash
   python report.py processed_2025-11-29_XXXX.json
   ```
4. If satisfied, run without limit on full first page:
   ```bash
   python gmail_manager.py
   ```

### Understanding Email Actions

When an email is processed, it may undergo one of these actions:

- **labeled**: A label from a matching rule was applied
- **marked_important**: A matching rule marked it as important
- **archived**: A matching rule archived it (removed from Inbox)
- **won't_archive**: Matched a rule but archival conditions weren't met
- **will_archive_later**: Email is scheduled for future archival based on age
- **none**: Matched a rule but no actions were taken

### Debugging

Enable debug logging:
```bash
LOG_LEVEL=DEBUG python gmail_manager.py --limit 1
```

This shows detailed decision-making for each email against each rule.

## Project Structure

- `gmail_manager.py` - Main application
- `config.yaml` - Rule definitions
- `report.py` - Report generator for processed emails
- `rule_matcher.py` - Rule matching logic (regex)
- `pagination_fetcher.py` - Gmail API pagination handling
- `rules_usage.py` - Track rule usage statistics
- `table_formatter.py` - Format output tables
- `app_config.py` - Centralized path configuration
- `processed_*.json` - Historical run outputs (for auditing)
- `rules_usage.json` - Accumulated rule usage statistics

## Important Notes

- The application requires `gwsa` (gworkspace-access CLI) to be installed and configured
- All email operations are real - they actually label, mark important, and archive emails
- The `--limit` flag is useful for testing rule changes safely
- All operations are logged to JSON for auditing
- Rules are processed in order: important-marking rules first, then others
