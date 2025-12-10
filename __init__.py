"""
Dropbox File Uploader Package

A robust utility for uploading files to Dropbox with comprehensive error handling.
Designed for both CLI usage and GitHub Actions environments.

Usage:
    # As a module
    from dropbox_uploader import upload_file, DropboxUploader
    
    # Simple upload
    upload_file("my_report_2024-01-15_14-30.md", dropbox_folder="/Reports")
    
    # With context manager
    with DropboxUploader() as uploader:
        uploader.upload("file1.md", "/Reports")
        uploader.upload("file2.md", "/Reports")

    # From command line
    python -m dropbox_uploader my_file.md --folder /Reports
"""

from .dropbox_uploader import (
    DropboxUploader,
    upload_file,
    DropboxUploaderError,
    AuthenticationError,
    FileNotFoundError,
    UploadError,
    logger,
)

__version__ = "1.0.0"
__all__ = [
    "DropboxUploader",
    "upload_file",
    "DropboxUploaderError",
    "AuthenticationError",
    "FileNotFoundError",
    "UploadError",
    "logger",
]
