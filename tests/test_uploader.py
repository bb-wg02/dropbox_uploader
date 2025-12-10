"""
Basic high-level tests for dropbox_uploader.

Run with: pytest tests/ -v
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from dropbox_uploader import (
    DropboxUploader,
    upload_file,
    AuthenticationError,
    FileNotFoundError as UploaderFileNotFoundError,
    UploadError,
)


# --- Fixtures ---

@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary markdown file for testing."""
    file_path = tmp_path / "test_report_2024-01-15_14-30.md"
    file_path.write_text("# Test Report\n\nSome content here.")
    return file_path


@pytest.fixture
def mock_dropbox_client():
    """Create a mock Dropbox client."""
    with patch("dropbox_uploader.dropbox_uploader.dropbox.Dropbox") as mock:
        client = Mock()
        client.users_get_current_account.return_value = Mock(
            name=Mock(display_name="Test User")
        )
        client.files_upload.return_value = Mock(path_display="/Reports/test.md")
        mock.return_value = client
        yield client


# --- Authentication Tests ---

class TestAuthentication:
    
    def test_missing_token_raises_error(self):
        """Should raise AuthenticationError when no token is provided."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DROPBOX_ACCESS_TOKEN", None)
            with pytest.raises(AuthenticationError, match="No Dropbox access token"):
                DropboxUploader()

    def test_token_from_environment(self, mock_dropbox_client):
        """Should read token from environment variable."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test_token"}):
            uploader = DropboxUploader()
            assert uploader.access_token == "test_token"

    def test_token_from_parameter(self, mock_dropbox_client):
        """Should accept token as parameter."""
        uploader = DropboxUploader(access_token="direct_token")
        assert uploader.access_token == "direct_token"

    def test_parameter_token_overrides_environment(self, mock_dropbox_client):
        """Parameter token should take precedence over environment."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "env_token"}):
            uploader = DropboxUploader(access_token="param_token")
            assert uploader.access_token == "param_token"


# --- Path Handling Tests ---

class TestPathHandling:

    def test_normalize_dropbox_path_adds_leading_slash(self):
        """Should add leading slash if missing."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader._normalize_dropbox_path("Reports/2024")
            assert result == "/Reports/2024"

    def test_normalize_dropbox_path_preserves_leading_slash(self):
        """Should preserve existing leading slash."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader._normalize_dropbox_path("/Reports/2024")
            assert result == "/Reports/2024"

    def test_normalize_dropbox_path_converts_backslashes(self):
        """Should convert Windows backslashes to forward slashes."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader._normalize_dropbox_path("\\Reports\\2024")
            assert result == "/Reports/2024"

    def test_normalize_dropbox_path_removes_double_slashes(self):
        """Should remove double slashes."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader._normalize_dropbox_path("/Reports//2024//file.md")
            assert result == "/Reports/2024/file.md"

    def test_resolve_git_bash_path(self):
        """Should convert Git Bash /c/... paths to C:/..."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            # Note: resolve() will fail on non-existent paths, so we test the conversion logic
            result = uploader._resolve_local_path("/c/Users/test/file.md")
            assert str(result).startswith("C:")

    def test_resolve_cygdrive_path(self):
        """Should convert Cygwin /cygdrive/c/... paths."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader._resolve_local_path("/cygdrive/c/Users/test/file.md")
            assert str(result).startswith("C:")


# --- File Validation Tests ---

class TestFileValidation:

    def test_file_not_found_raises_error(self, mock_dropbox_client):
        """Should raise error when file doesn't exist."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            with pytest.raises(UploaderFileNotFoundError, match="File not found"):
                uploader.upload("/nonexistent/path/file.md")

    def test_directory_raises_error(self, mock_dropbox_client, tmp_path):
        """Should raise error when path is a directory."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            with pytest.raises(UploaderFileNotFoundError, match="not a file"):
                uploader.upload(str(tmp_path))


# --- Upload Tests ---

class TestUpload:

    def test_successful_upload(self, mock_dropbox_client, temp_file):
        """Should upload file and return Dropbox path."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader.upload(str(temp_file), dropbox_folder="/Reports")
            
            assert result == "/Reports/test.md"
            mock_dropbox_client.files_upload.assert_called_once()

    def test_upload_with_custom_filename(self, mock_dropbox_client, temp_file):
        """Should use custom filename when provided."""
        mock_dropbox_client.files_upload.return_value = Mock(
            path_display="/Reports/custom_name.md"
        )
        
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            result = uploader.upload(
                str(temp_file),
                dropbox_folder="/Reports",
                filename="custom_name.md"
            )
            
            assert result == "/Reports/custom_name.md"

    def test_upload_preserves_original_filename(self, mock_dropbox_client, temp_file):
        """Should use original filename by default."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            uploader = DropboxUploader()
            uploader.upload(str(temp_file), dropbox_folder="/Reports")
            
            call_args = mock_dropbox_client.files_upload.call_args
            uploaded_path = call_args[0][1]  # Second positional arg is path
            assert "test_report_2024-01-15_14-30.md" in uploaded_path


# --- Context Manager Tests ---

class TestContextManager:

    def test_context_manager_closes_client(self, mock_dropbox_client):
        """Should close client when exiting context."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            with DropboxUploader() as uploader:
                _ = uploader.client  # Force client creation
            
            mock_dropbox_client.close.assert_called_once()

    def test_context_manager_closes_on_exception(self, mock_dropbox_client):
        """Should close client even when exception occurs."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            try:
                with DropboxUploader() as uploader:
                    _ = uploader.client
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            mock_dropbox_client.close.assert_called_once()


# --- Convenience Function Tests ---

class TestUploadFileFunction:

    def test_upload_file_function(self, mock_dropbox_client, temp_file):
        """Should work as a simple one-liner."""
        with patch.dict(os.environ, {"DROPBOX_ACCESS_TOKEN": "test"}):
            result = upload_file(str(temp_file), dropbox_folder="/Reports")
            assert result == "/Reports/test.md"
