"""
Image Processor Module

Handles image file operations including path resolution, file reading,
and base64 encoding for Claude Vision API.
"""

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Dict, List

from .exceptions import ObsidianClaudeError

logger = logging.getLogger(__name__)


class ImageProcessingError(ObsidianClaudeError):
    """Raised when image processing fails."""
    pass


class ImageProcessor:
    """
    Handles image file operations for OCR processing.

    Responsibilities:
    - Resolve image paths in Obsidian vault
    - Read image files
    - Encode images to base64
    - Validate image formats and sizes
    """

    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    def __init__(
        self,
        vault_path: str,
        attachment_folders: Optional[List[str]] = None,
        max_file_size_mb: int = 10
    ):
        """
        Initialize the image processor.

        Args:
            vault_path: Path to Obsidian vault root
            attachment_folders: List of attachment folder names to search
            max_file_size_mb: Maximum allowed file size in MB
        """
        self.vault_path = Path(vault_path)
        self.attachment_folders = attachment_folders or ['_attachments', 'assets', 'images']
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        logger.info(f"Initialized ImageProcessor for vault: {vault_path}")

    def _is_within_vault(self, path: Path) -> bool:
        """
        Check if a resolved path is within the vault boundaries.

        Args:
            path: Resolved path to check

        Returns:
            True if path is within vault, False otherwise
        """
        try:
            # Resolve both paths to absolute, canonical forms
            resolved_path = path.resolve()
            resolved_vault = self.vault_path.resolve()

            # Check if the resolved path is relative to vault root
            resolved_path.relative_to(resolved_vault)
            return True
        except (ValueError, OSError):
            # relative_to() raises ValueError if not a subpath
            # OSError can occur with broken symlinks or permission issues
            return False

    def resolve_image_path(
        self,
        image_filename: str,
        source_note_path: Optional[str] = None
    ) -> Optional[Path]:
        """
        Resolve an image filename to its full path in the vault.

        Searches in order:
        1. Same directory as source note (if provided)
        2. Configured attachment folders
        3. Vault root

        Args:
            image_filename: Name of image file (e.g., "sketch.jpg")
            source_note_path: Path to source note (for relative resolution)

        Returns:
            Full path to image file, or None if not found

        Raises:
            ImageProcessingError: If resolved path is outside vault boundaries
        """
        # Search in same directory as source note
        if source_note_path:
            source_dir = self.vault_path / Path(source_note_path).parent
            candidate = source_dir / image_filename
            if candidate.exists() and candidate.is_file():
                # Validate vault boundary
                if not self._is_within_vault(candidate):
                    logger.error(f"Path traversal attempt detected: {candidate}")
                    raise ImageProcessingError(f"Image path outside vault: {image_filename}")
                logger.debug(f"Found image in source directory: {candidate}")
                return candidate

        # Search in attachment folders
        for folder in self.attachment_folders:
            candidate = self.vault_path / folder / image_filename
            if candidate.exists() and candidate.is_file():
                # Validate vault boundary
                if not self._is_within_vault(candidate):
                    logger.error(f"Path traversal attempt detected: {candidate}")
                    raise ImageProcessingError(f"Image path outside vault: {image_filename}")
                logger.debug(f"Found image in attachment folder: {candidate}")
                return candidate

        # Search in vault root
        candidate = self.vault_path / image_filename
        if candidate.exists() and candidate.is_file():
            # Validate vault boundary
            if not self._is_within_vault(candidate):
                logger.error(f"Path traversal attempt detected: {candidate}")
                raise ImageProcessingError(f"Image path outside vault: {image_filename}")
            logger.debug(f"Found image in vault root: {candidate}")
            return candidate

        logger.warning(f"Image not found: {image_filename}")
        return None

    def validate_image(self, image_path: Path) -> None:
        """
        Validate image format and size.

        Args:
            image_path: Path to image file

        Raises:
            ImageProcessingError: If validation fails
        """
        # Check format
        if image_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            raise ImageProcessingError(
                f"Unsupported image format: {image_path.suffix}. "
                f"Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Check file size
        file_size = image_path.stat().st_size
        if file_size > self.max_file_size_bytes:
            size_mb = file_size / (1024 * 1024)
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            raise ImageProcessingError(
                f"Image too large: {size_mb:.2f}MB (max: {max_mb}MB)"
            )

    def get_image_mime_type(self, image_path: Path) -> str:
        """
        Get MIME type for image file.

        Args:
            image_path: Path to image file

        Returns:
            MIME type string (e.g., "image/jpeg")
        """
        mime_type, _ = mimetypes.guess_type(str(image_path))

        if not mime_type:
            # Fallback based on extension
            ext = image_path.suffix.lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            mime_type = mime_map.get(ext, 'image/jpeg')

        return mime_type

    def read_and_encode_image(self, image_path: Path) -> Dict[str, str]:
        """
        Read image file and encode to base64.

        Args:
            image_path: Path to image file

        Returns:
            Dict with 'data' (base64 string) and 'mime_type'

        Raises:
            ImageProcessingError: If reading or encoding fails
        """
        try:
            # Validate before reading
            self.validate_image(image_path)

            # Read file
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Encode to base64
            encoded_data = base64.b64encode(image_data).decode('utf-8')

            # Get MIME type
            mime_type = self.get_image_mime_type(image_path)

            logger.info(f"Encoded image: {image_path.name} ({len(image_data)} bytes)")

            return {
                'data': encoded_data,
                'mime_type': mime_type
            }

        except ImageProcessingError:
            raise

        except Exception as e:
            logger.error(f"Failed to read/encode image {image_path}: {e}")
            raise ImageProcessingError(f"Failed to read image: {e}")

    def process_image(
        self,
        image_filename: str,
        source_note_path: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Complete image processing pipeline: resolve, read, encode.

        Args:
            image_filename: Name of image file
            source_note_path: Path to source note

        Returns:
            Dict with 'data' (base64) and 'mime_type'

        Raises:
            ImageProcessingError: If any step fails
        """
        # Resolve path
        image_path = self.resolve_image_path(image_filename, source_note_path)

        if not image_path:
            raise ImageProcessingError(f"Image not found: {image_filename}")

        # Read and encode
        return self.read_and_encode_image(image_path)
