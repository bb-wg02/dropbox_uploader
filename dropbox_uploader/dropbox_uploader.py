"""
Dropbox File Uploader

A robust utility for uploading files to Dropbox with comprehensive error handling.
Designed for both CLI usage and GitHub Actions environments.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

try:
    import dropbox
    from dropbox.exceptions import ApiError, AuthError
    from dropbox.files import WriteMode, CommitInfo, UploadSessionCursor
except ImportError:
    print("Error: dropbox package not installed. Run: pip install dropbox")
    sys.exit(1)

# Configure logging with immediate output
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
# Ensure output is not buffered
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# Constants
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB chunks for large file uploads
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


class DropboxUploaderError(Exception):
    """Base exception for Dropbox uploader errors."""
    pass


class AuthenticationError(DropboxUploaderError):
    """Raised when authentication fails."""
    pass


class FileNotFoundError(DropboxUploaderError):
    """Raised when the source file doesn't exist."""
    pass


class UploadError(DropboxUploaderError):
    """Raised when upload fails after retries."""
    pass


class DropboxUploader:
    """
    Handles file uploads to Dropbox with retry logic and chunked uploads for large files.
    """

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize the Dropbox uploader.

        Preferred auth (auto-refresh):
          - DROPBOX_APP_KEY
          - DROPBOX_APP_SECRET
          - DROPBOX_REFRESH_TOKEN

        Legacy fallback:
          - explicit access_token argument, or
          - DROPBOX_ACCESS_TOKEN environment variable
        """
        # Explicit access token (e.g. from CLI --token)
        self._explicit_access_token = access_token

        # Legacy env-based access token
        self._env_access_token = os.environ.get("DROPBOX_ACCESS_TOKEN")

        # Preferred refresh-token-based auth
        self._app_key = os.environ.get("DROPBOX_APP_KEY")
        self._app_secret = os.environ.get("DROPBOX_APP_SECRET")
        self._refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")

        self._client: Optional[dropbox.Dropbox] = None


    @property
    def client(self) -> dropbox.Dropbox:
        """Lazy initialization of Dropbox client."""
        if self._client is None:
            # Preferred: refresh-token-based auth if all pieces are present
            if self._refresh_token and self._app_key and self._app_secret:
                self._client = dropbox.Dropbox(
                    oauth2_refresh_token=self._refresh_token,
                    app_key=self._app_key,
                    app_secret=self._app_secret,
                )
            else:
                # Legacy: fall back to access token
                access_token = self._explicit_access_token or self._env_access_token
                if not access_token:
                    raise AuthenticationError(
                        "No Dropbox credentials provided.\n"
                        "Preferred: set DROPBOX_APP_KEY, DROPBOX_APP_SECRET, and DROPBOX_REFRESH_TOKEN.\n"
                        "Fallback: set DROPBOX_ACCESS_TOKEN or pass --token."
                    )
                self._client = dropbox.Dropbox(access_token)

            self._verify_connection()

        return self._client


    def _verify_connection(self) -> None:
        """Verify the Dropbox connection and token validity."""
        try:
            account = self._client.users_get_current_account()
            print(f"✓ Connected as: {account.name.display_name}")
        except AuthError as e:
            raise AuthenticationError(f"Invalid Dropbox credentials: {e}")
        except Exception as e:
            raise DropboxUploaderError(f"Failed to connect to Dropbox: {e}")

    def _normalize_dropbox_path(self, path: str) -> str:
        """
        Normalize the Dropbox destination path.

        Args:
            path: The destination path in Dropbox.

        Returns:
            Normalized path starting with '/'.
        """
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path

        # Normalize path separators (Windows compatibility)
        path = path.replace("\\", "/")

        # Remove double slashes
        while "//" in path:
            path = path.replace("//", "/")

        return path

    def _upload_small_file(
        self,
        file_path: Path,
        dropbox_path: str,
        overwrite: bool = True
    ) -> dropbox.files.FileMetadata:
        """
        Upload a small file (< 150MB) in a single request.

        Args:
            file_path: Local file path.
            dropbox_path: Destination path in Dropbox.
            overwrite: Whether to overwrite existing files.

        Returns:
            File metadata from Dropbox.
        """
        mode = WriteMode.overwrite if overwrite else WriteMode.add

        with open(file_path, "rb") as f:
            return self.client.files_upload(
                f.read(),
                dropbox_path,
                mode=mode,
            )

    def _upload_large_file(
        self,
        file_path: Path,
        dropbox_path: str,
        file_size: int,
        overwrite: bool = True
    ) -> dropbox.files.FileMetadata:
        """
        Upload a large file using chunked upload sessions.

        Args:
            file_path: Local file path.
            dropbox_path: Destination path in Dropbox.
            file_size: Size of the file in bytes.
            overwrite: Whether to overwrite existing files.

        Returns:
            File metadata from Dropbox.
        """
        mode = WriteMode.overwrite if overwrite else WriteMode.add

        with open(file_path, "rb") as f:
            # Start upload session
            session_start = self.client.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = UploadSessionCursor(
                session_id=session_start.session_id,
                offset=f.tell()
            )
            commit = CommitInfo(path=dropbox_path, mode=mode)

            # Upload chunks
            while f.tell() < file_size:
                remaining = file_size - f.tell()

                if remaining <= CHUNK_SIZE:
                    # Final chunk
                    return self.client.files_upload_session_finish(
                        f.read(remaining),
                        cursor,
                        commit
                    )
                else:
                    # Intermediate chunk
                    self.client.files_upload_session_append_v2(
                        f.read(CHUNK_SIZE),
                        cursor
                    )
                    cursor.offset = f.tell()
                    pct = (f.tell() / file_size) * 100
                    print(f"  {pct:.0f}% uploaded...", end='\r')

        raise UploadError("Unexpected end of file during chunked upload")

    def _resolve_local_path(self, local_path: str) -> Path:
        """
        Resolve a local file path, handling Git Bash and Windows path formats.

        Git Bash uses Unix-style paths like /c/Users/... or /d/Projects/...
        Windows uses C:\\Users\\... or C:/Users/...
        This method normalizes both to work correctly.

        Args:
            local_path: The input path string.

        Returns:
            Resolved Path object.
        """
        path_str = str(local_path)

        # Handle Git Bash absolute paths: /c/Users/... -> C:/Users/...
        # Git Bash uses /driveletter/... format for Windows drives
        if len(path_str) >= 3 and path_str[0] == '/' and path_str[2] == '/':
            drive_letter = path_str[1]
            if drive_letter.isalpha():
                path_str = f"{drive_letter.upper()}:{path_str[2:]}"

        # Also handle /cygdrive/c/... format (Cygwin/MSYS2)
        if path_str.startswith('/cygdrive/') and len(path_str) >= 12:
            drive_letter = path_str[10]
            if drive_letter.isalpha():
                path_str = f"{drive_letter.upper()}:{path_str[11:]}"

        return Path(path_str).resolve()

    def upload(
        self,
        local_path: str,
        dropbox_folder: str = "/",
        filename: Optional[str] = None,
        overwrite: bool = True
    ) -> str:
        """
        Upload a file to Dropbox with automatic retry and chunked upload for large files.

        Args:
            local_path: Path to the local file to upload.
            dropbox_folder: Destination folder in Dropbox (default: root).
            filename: Custom filename in Dropbox (default: use original filename).
            overwrite: Whether to overwrite existing files (default: True).

        Returns:
            The Dropbox path where the file was uploaded.

        Raises:
            FileNotFoundError: If the local file doesn't exist.
            UploadError: If upload fails after all retries.
        """
        file_path = self._resolve_local_path(local_path)

        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {file_path}")

        # Determine destination path
        dest_filename = filename or file_path.name
        dropbox_path = self._normalize_dropbox_path(f"{dropbox_folder}/{dest_filename}")

        file_size = file_path.stat().st_size
        size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024*1024):.1f} MB"
        
        print(f"→ Uploading: {file_path.name} ({size_str})")
        print(f"→ Destination: {dropbox_path}")

        # Retry loop
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Choose upload method based on file size
                if file_size <= 150 * 1024 * 1024:  # 150 MB threshold
                    metadata = self._upload_small_file(file_path, dropbox_path, overwrite)
                else:
                    metadata = self._upload_large_file(file_path, dropbox_path, file_size, overwrite)

                print(f"✓ Upload complete: {metadata.path_display}")
                return metadata.path_display

            except AuthError as e:
                raise AuthenticationError(f"Authentication failed: {e}")

            except ApiError as e:
                last_error = e
                error_msg = str(e.error) if hasattr(e, 'error') else str(e)

                # Check for specific error types
                if "path/conflict" in error_msg.lower():
                    if overwrite:
                        print(f"⚠ Conflict detected, retrying...")
                    else:
                        raise UploadError(f"File already exists at {dropbox_path}")

                elif "insufficient_space" in error_msg.lower():
                    raise UploadError("Insufficient space in Dropbox account")

                elif attempt < MAX_RETRIES:
                    print(f"⚠ Attempt {attempt}/{MAX_RETRIES} failed. Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise UploadError(f"Upload failed after {MAX_RETRIES} attempts: {error_msg}")

            except (ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    print(f"⚠ Connection error (attempt {attempt}/{MAX_RETRIES}). Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise UploadError(f"Connection failed after {MAX_RETRIES} attempts: {e}")

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    print(f"⚠ Error (attempt {attempt}/{MAX_RETRIES}): {e}. Retrying...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise UploadError(f"Upload failed: {e}")

        raise UploadError(f"Upload failed after {MAX_RETRIES} attempts: {last_error}")

    def close(self) -> None:
        """Close the Dropbox client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.debug("Dropbox client closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def upload_file(
    local_path: str,
    dropbox_folder: str = "/",
    access_token: Optional[str] = None,
    filename: Optional[str] = None,
    overwrite: bool = True
) -> str:
    """
    Convenience function to upload a file to Dropbox.

    Args:
        local_path: Path to the local file to upload.
        dropbox_folder: Destination folder in Dropbox (default: root).
        access_token: Dropbox access token (default: from environment).
        filename: Custom filename (default: use original).
        overwrite: Whether to overwrite existing files (default: True).

    Returns:
        The Dropbox path where the file was uploaded.
    """
    with DropboxUploader(access_token) as uploader:
        return uploader.upload(local_path, dropbox_folder, filename, overwrite)