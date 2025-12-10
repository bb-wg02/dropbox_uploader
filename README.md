# Dropbox File Uploader

A robust Python package for uploading files to Dropbox with comprehensive error handling. Designed to work seamlessly on Windows desktops and in GitHub Actions environments.

## Features

- **Automatic retry logic** - Retries failed uploads up to 3 times with exponential backoff
- **Chunked uploads** - Handles large files (>150MB) using upload sessions
- **Cross-platform** - Works on Windows (CMD, PowerShell, Git Bash), macOS, and Linux
- **Git Bash compatible** - Handles `/c/Users/...` style paths automatically
- **GitHub Actions ready** - Sets output variables for workflow integration
- **Graceful error handling** - Clear error messages for common failure scenarios
- **Flexible authentication** - Token via environment variable or direct parameter

## Installation

```bash
# Install from the package directory
pip install .

# Or install with dev dependencies
pip install ".[dev]"

# Or install just the dependency manually
pip install dropbox
```

## Setup: Getting a Dropbox Access Token

1. Go to the [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. Click "Create app"
3. Choose "Scoped access"
4. Choose "Full Dropbox" or "App folder" (depending on your needs)
5. Name your app and click "Create app"
6. Under "Permissions", enable `files.content.write` and `files.content.read`
7. Go to "Settings" tab and click "Generate" under "Generated access token"
8. Copy the token

## Usage

### Command Line

```bash
# Set your access token (do this once per session)
# Windows CMD:
set DROPBOX_ACCESS_TOKEN=your_token_here

# Windows PowerShell:
$env:DROPBOX_ACCESS_TOKEN = "your_token_here"

# Linux/macOS/Git Bash:
export DROPBOX_ACCESS_TOKEN=your_token_here

# Upload a file to root folder
python -m dropbox_uploader my_report_2024-01-15_14-30.md

# Upload to a specific folder
python -m dropbox_uploader my_file.md --folder /Reports/2024

# Use a custom filename
python -m dropbox_uploader local_file.md --filename custom_name.md

# Verbose output
python -m dropbox_uploader my_file.md -v

# Quiet mode (only errors)
python -m dropbox_uploader my_file.md -q
```

### Path Formats

The uploader handles multiple path formats automatically:

```bash
# All of these work in Git Bash:
python -m dropbox_uploader ./report.md                    # Relative path
python -m dropbox_uploader /c/Users/me/report.md          # Git Bash absolute
python -m dropbox_uploader /d/Projects/output/report.md   # Other drives
python -m dropbox_uploader "C:/Users/me/report.md"        # Windows style (quoted)
```

### Python API

```python
from dropbox_uploader import upload_file, DropboxUploader

# Simple one-liner upload
dropbox_path = upload_file(
    "my_report_2024-01-15_14-30.md",
    dropbox_folder="/Reports/2024"
)
print(f"Uploaded to: {dropbox_path}")

# Using context manager for multiple uploads
with DropboxUploader() as uploader:
    uploader.upload("file1.md", "/Reports")
    uploader.upload("file2.md", "/Reports")
    uploader.upload("file3.md", "/Archives")

# Pass token directly (useful for testing)
with DropboxUploader(access_token="your_token") as uploader:
    uploader.upload("my_file.md", "/Backups")
```

### Integration with Your Python Script

```python
import os
from datetime import datetime
from dropbox_uploader import upload_file, UploadError, AuthenticationError

def generate_report():
    """Your existing report generation logic."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"report_{timestamp}.md"
    
    # Generate your markdown content
    content = "# My Report\n\nThis is the report content..."
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    return filename

def main():
    # Generate the report
    local_file = generate_report()
    print(f"Generated: {local_file}")
    
    # Upload to Dropbox
    try:
        dropbox_path = upload_file(
            local_file,
            dropbox_folder="/Reports/Automated"
        )
        print(f"Successfully uploaded to: {dropbox_path}")
        
        # Optionally clean up local file
        # os.remove(local_file)
        
    except AuthenticationError:
        print("Error: Check your DROPBOX_ACCESS_TOKEN")
        raise
    except UploadError as e:
        print(f"Upload failed: {e}")
        raise

if __name__ == "__main__":
    main()
```

## GitHub Actions Integration

### Workflow Example

```yaml
name: Generate and Upload Report

on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8 AM UTC
  workflow_dispatch:

jobs:
  generate-report:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install dropbox
          # Or if using the package:
          # pip install ./dropbox_uploader
      
      - name: Generate report
        run: python your_script.py
      
      - name: Upload to Dropbox
        env:
          DROPBOX_ACCESS_TOKEN: ${{ secrets.DROPBOX_ACCESS_TOKEN }}
        run: |
          python -m dropbox_uploader report_*.md --folder /Reports/Automated
```

### Setting Up the Secret

1. Go to your GitHub repository
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `DROPBOX_ACCESS_TOKEN`
5. Value: Your Dropbox access token

## Error Handling

The package handles these common scenarios:

| Error Type | Description | Exit Code |
|------------|-------------|-----------|
| `AuthenticationError` | Invalid or expired token | 2 |
| `FileNotFoundError` | Local file doesn't exist | 1 |
| `UploadError` | Upload failed after retries | 3 |
| Network errors | Connection/timeout issues | 3 (after retries) |
| Insufficient space | Dropbox account full | 3 |

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DROPBOX_ACCESS_TOKEN` | Your Dropbox API token | (required) |
| `DROPBOX_FOLDER` | Default destination folder | `/` |

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `file` | Path to file to upload (required) |
| `-f, --folder` | Destination folder in Dropbox |
| `-n, --filename` | Custom filename in Dropbox |
| `-t, --token` | Dropbox access token (overrides env var) |
| `--no-overwrite` | Don't overwrite existing files |
| `-v, --verbose` | Enable debug output |
| `-q, --quiet` | Only show errors |

## Handling Large Files

Files larger than 150MB are automatically uploaded using Dropbox's chunked upload API. The upload progress is logged when using verbose mode:

```bash
python -m dropbox_uploader large_file.md -v
```

## Refreshing Long-Lived Tokens

Dropbox access tokens expire. For long-running automation, consider using refresh tokens:

1. In your Dropbox app settings, note your App Key and App Secret
2. Use OAuth2 to get a refresh token
3. Modify the uploader to use `dropbox.Dropbox.from_oauth2_flow()` or refresh tokens

For individual use with short-term automation, the standard access token approach works fine.

## License

MIT License - see LICENSE file for details.
