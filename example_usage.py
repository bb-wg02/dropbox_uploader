#!/usr/bin/env python
"""
Example: Integrating the Dropbox uploader with a report generation script.

This shows how to use the dropbox_uploader package with your existing
Python script that generates markdown files.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path if running as standalone script
sys.path.insert(0, str(Path(__file__).parent))

from dropbox_uploader import (
    upload_file,
    DropboxUploader,
    AuthenticationError,
    UploadError,
)


def generate_sample_report() -> str:
    """
    Simulates your existing report generation logic.
    Replace this with your actual report generation code.
    
    Returns:
        Path to the generated markdown file.
    """
    # Create timestamp to the minute (matching your requirement)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"report_{timestamp}.md"
    
    # Sample content - replace with your actual report content
    content = f"""# Automated Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

This is an automatically generated report.

## Data

| Metric | Value |
|--------|-------|
| Items Processed | 1,234 |
| Success Rate | 98.5% |
| Duration | 45.2s |

## Details

Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

### Section 1

More detailed information here...

### Section 2

Additional content...

---
*Report generated automatically*
"""
    
    # Write to file with UTF-8 encoding (important for Windows)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"Generated report: {filename} ({Path(filename).stat().st_size} bytes)")
    return filename


def upload_report_simple(local_file: str, folder: str = "/Reports") -> str:
    """
    Simple upload using the convenience function.
    Good for one-off uploads.
    """
    return upload_file(local_file, dropbox_folder=folder)


def upload_report_with_handling(local_file: str, folder: str = "/Reports") -> str:
    """
    Upload with explicit error handling and cleanup.
    Good for production use.
    """
    try:
        dropbox_path = upload_file(local_file, dropbox_folder=folder)
        print(f"✓ Uploaded to: {dropbox_path}")
        return dropbox_path
        
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        print("  Check that DROPBOX_ACCESS_TOKEN is set correctly")
        raise
        
    except UploadError as e:
        print(f"✗ Upload failed: {e}")
        print("  The file was saved locally, you can retry later")
        raise
        

def upload_multiple_files(files: list, folder: str = "/Reports") -> list:
    """
    Upload multiple files efficiently using a single connection.
    Good when you have multiple files to upload.
    """
    results = []
    
    with DropboxUploader() as uploader:
        for local_file in files:
            try:
                dropbox_path = uploader.upload(local_file, folder)
                results.append({"file": local_file, "path": dropbox_path, "success": True})
                print(f"✓ {local_file} -> {dropbox_path}")
            except Exception as e:
                results.append({"file": local_file, "error": str(e), "success": False})
                print(f"✗ {local_file}: {e}")
    
    return results


def main():
    """Main entry point demonstrating the workflow."""
    
    # Check for token
    if not os.environ.get("DROPBOX_ACCESS_TOKEN"):
        print("Error: DROPBOX_ACCESS_TOKEN environment variable not set")
        print()
        print("To set it:")
        print("  Windows CMD:    set DROPBOX_ACCESS_TOKEN=your_token")
        print("  PowerShell:     $env:DROPBOX_ACCESS_TOKEN = 'your_token'")
        print("  Linux/macOS:    export DROPBOX_ACCESS_TOKEN=your_token")
        sys.exit(1)
    
    # Step 1: Generate the report (your existing logic)
    print("=" * 50)
    print("Step 1: Generating report...")
    print("=" * 50)
    local_file = generate_sample_report()
    
    # Step 2: Upload to Dropbox
    print()
    print("=" * 50)
    print("Step 2: Uploading to Dropbox...")
    print("=" * 50)
    
    try:
        # You can customize the destination folder
        destination_folder = os.environ.get("DROPBOX_FOLDER", "/Reports/Automated")
        
        dropbox_path = upload_report_with_handling(local_file, destination_folder)
        
        print()
        print("=" * 50)
        print("Success!")
        print(f"  Local file:  {local_file}")
        print(f"  Dropbox:     {dropbox_path}")
        print("=" * 50)
        
        # Optional: Clean up local file after successful upload
        # os.remove(local_file)
        # print(f"Cleaned up local file: {local_file}")
        
    except Exception as e:
        print()
        print("=" * 50)
        print(f"Failed: {e}")
        print(f"Local file preserved: {local_file}")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
