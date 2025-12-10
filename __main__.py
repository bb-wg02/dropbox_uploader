#!/usr/bin/env python
"""
Command-line interface for Dropbox file uploader.
Supports both Windows CLI and GitHub Actions environments.
"""

import argparse
import sys
import os
from pathlib import Path

from dropbox_uploader import (
    DropboxUploader,
    DropboxUploaderError,
    AuthenticationError,
    FileNotFoundError as UploaderFileNotFoundError,
    UploadError,
    logger,
)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Upload files to Dropbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload a file to root folder
  python -m dropbox_uploader my_report_2024-01-15_14-30.md

  # Upload to a specific folder
  python -m dropbox_uploader my_file.md --folder /Reports/2024

  # Use a custom filename
  python -m dropbox_uploader local_file.md --filename custom_name.md

  # Provide token directly (not recommended for security)
  python -m dropbox_uploader my_file.md --token YOUR_TOKEN

Environment Variables:
  DROPBOX_ACCESS_TOKEN    Your Dropbox API access token (required)
  DROPBOX_FOLDER          Default destination folder (optional)
""",
    )

    parser.add_argument(
        "file",
        help="Path to the file to upload",
    )

    parser.add_argument(
        "-f", "--folder",
        default=os.environ.get("DROPBOX_FOLDER", "/"),
        help="Destination folder in Dropbox (default: / or DROPBOX_FOLDER env var)",
    )

    parser.add_argument(
        "-n", "--filename",
        help="Custom filename in Dropbox (default: use original filename)",
    )

    parser.add_argument(
        "-t", "--token",
        help="Dropbox access token (default: from DROPBOX_ACCESS_TOKEN env var)",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Don't overwrite existing files",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )

    return parser.parse_args()


def main():
    """Main entry point for CLI."""
    args = parse_args()

    # Configure logging level
    if args.quiet:
        logger.setLevel("ERROR")
    elif args.verbose:
        logger.setLevel("DEBUG")

    # Validate file exists before attempting upload
    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    if not file_path.is_file():
        logger.error(f"Path is not a file: {args.file}")
        sys.exit(1)

    try:
        with DropboxUploader(access_token=args.token) as uploader:
            dropbox_path = uploader.upload(
                local_path=args.file,
                dropbox_folder=args.folder,
                filename=args.filename,
                overwrite=not args.no_overwrite,
            )

        if not args.quiet:
            print(f"Successfully uploaded to: {dropbox_path}")

        # Set GitHub Actions output if running in that environment
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"dropbox_path={dropbox_path}\n")

        sys.exit(0)

    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Make sure DROPBOX_ACCESS_TOKEN is set correctly.")
        sys.exit(2)

    except UploaderFileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    except UploadError as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(3)

    except DropboxUploaderError as e:
        logger.error(f"Error: {e}")
        sys.exit(4)

    except KeyboardInterrupt:
        logger.info("Upload cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(99)


if __name__ == "__main__":
    main()
