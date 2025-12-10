# Dropbox File Uploader

A Python package for uploading files to Dropbox. Works on Windows (Git Bash), macOS, Linux, and GitHub Actions.

## Features

- Automatic retry (3 attempts)
- Chunked uploads for large files (>150MB)
- Cross-platform path handling

## Installation
```bash
cd ~/coding/dropbox_uploader
uv pip install -e .
```

## Setup: Get a Dropbox Access Token

1. Go to https://www.dropbox.com/developers/apps
2. Click **Create app**
3. Select **Scoped access** → **Full Dropbox**
4. Name it, click **Create app**
5. Go to **Permissions** tab, enable `files.content.write` and `files.content.read`, click **Submit**
6. Go to **Settings** tab, click **Generate** under "Generated access token"
7. Copy the token

Add to your `~/.bashrc`:
```bash
export DROPBOX_ACCESS_TOKEN="your_token_here"
```

## Usage

### Command Line
```bash
# Upload a file
dropbox-upload myfile.md --folder //Reports

# Or without leading slash (recommended for Git Bash)
dropbox-upload myfile.md --folder Reports/2024
```

**Git Bash note:** Use `//folder` or `folder` (no leading slash) to avoid path mangling.

### Python API
```python
from dropbox_uploader import upload_file

upload_file("report.md", dropbox_folder="/Reports")
```

## CLI Options

| Argument | Description |
|----------|-------------|
| `file` | File to upload (required) |
| `-f, --folder` | Dropbox destination folder |
| `-n, --filename` | Rename file in Dropbox |
| `--no-overwrite` | Don't overwrite existing files |
| `-v, --verbose` | Debug output |
| `-q, --quiet` | Errors only |

## GitHub Actions
```yaml
- name: Upload to Dropbox
  env:
    DROPBOX_ACCESS_TOKEN: ${{ secrets.DROPBOX_ACCESS_TOKEN }}
  run: python -m dropbox_uploader report.md --folder /Reports
```

Add `DROPBOX_ACCESS_TOKEN` to your repository secrets.

## Token Expiration

Tokens expire after a few hours. For automation, regenerate as needed or implement refresh tokens.