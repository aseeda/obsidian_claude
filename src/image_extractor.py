"""
Image Extractor Module

Extracts text from images using Claude Vision API.
Handles Phase 1 of the two-phase image processing workflow.
"""

import logging
from typing import Dict, List, Optional

from .image_processor import ImageProcessor, ImageProcessingError
from .claude_client import ClaudeClient
from .exceptions import ClaudeAPIError

logger = logging.getLogger(__name__)


class ImageExtractor:
    """
    Extracts text from images using Claude Vision API.

    Responsibilities:
    - Process multiple images sequentially
    - Send vision requests to Claude API
    - Collect and return extracted text
    - Handle errors gracefully
    """

    DEFAULT_OCR_PROMPT = (
        "Extract all text from this image. "
        "Preserve the original formatting, structure, and layout as much as possible. "
        "If the image contains handwritten text, transcribe it carefully. "
        "If there is no text in the image, respond with 'No text found'."
    )

    def __init__(
        self,
        image_processor: ImageProcessor,
        claude_client: ClaudeClient,
        ocr_prompt: Optional[str] = None,
        max_images_per_request: int = 5
    ):
        """
        Initialize the image extractor.

        Args:
            image_processor: ImageProcessor instance for file operations
            claude_client: ClaudeClient instance for API calls
            ocr_prompt: Custom OCR extraction prompt (uses default if None)
            max_images_per_request: Maximum images to process per request
        """
        self.image_processor = image_processor
        self.claude_client = claude_client
        self.ocr_prompt = ocr_prompt or self.DEFAULT_OCR_PROMPT
        self.max_images_per_request = max_images_per_request

        logger.info("Initialized ImageExtractor")

    def extract_text_from_image(
        self,
        image_filename: str,
        source_note_path: Optional[str] = None
    ) -> str:
        """
        Extract text from a single image using Claude Vision API.

        Args:
            image_filename: Name of image file
            source_note_path: Path to source note (for path resolution)

        Returns:
            Extracted text from image

        Raises:
            ImageProcessingError: If image processing fails
            ClaudeAPIError: If API request fails
        """
        try:
            # Process image (resolve path, read, encode)
            logger.info(f"Processing image: {image_filename}")
            image_data = self.image_processor.process_image(
                image_filename,
                source_note_path
            )

            # Send vision request to Claude
            logger.info(f"Sending vision request for: {image_filename}")
            extracted_text = self.claude_client.process_vision_request(
                prompt=self.ocr_prompt,
                image_data=image_data['data'],
                mime_type=image_data['mime_type']
            )

            logger.info(f"Extracted {len(extracted_text)} chars from {image_filename}")
            return extracted_text

        except ImageProcessingError as e:
            logger.error(f"Image processing error for {image_filename}: {e}")
            return f"[Error processing image: {e}]"

        except ClaudeAPIError as e:
            logger.error(f"Claude API error for {image_filename}: {e}")
            return f"[Error extracting text: {e}]"

        except Exception as e:
            logger.error(f"Unexpected error processing {image_filename}: {e}")
            return f"[Error: {e}]"

    def extract_text_from_images(
        self,
        image_filenames: List[str],
        source_note_path: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Extract text from multiple images sequentially.

        Args:
            image_filenames: List of image filenames
            source_note_path: Path to source note

        Returns:
            Dict mapping filename -> extracted text
        """
        if not image_filenames:
            return {}

        # Limit number of images
        if len(image_filenames) > self.max_images_per_request:
            logger.warning(
                f"Too many images ({len(image_filenames)}), "
                f"processing first {self.max_images_per_request}"
            )
            image_filenames = image_filenames[:self.max_images_per_request]

        logger.info(f"Extracting text from {len(image_filenames)} image(s)")

        extracted_text = {}

        for image_filename in image_filenames:
            text = self.extract_text_from_image(image_filename, source_note_path)
            extracted_text[image_filename] = text

        logger.info(f"Completed extraction for {len(extracted_text)} image(s)")
        return extracted_text

    def build_context_with_image_text(
        self,
        original_context: str,
        extracted_image_text: Dict[str, str]
    ) -> str:
        """
        Build enhanced context by appending extracted image text.

        Args:
            original_context: Original note context
            extracted_image_text: Dict of filename -> extracted text

        Returns:
            Enhanced context with image text appended
        """
        if not extracted_image_text:
            return original_context

        # Build image text section
        image_sections = ["\n\n**Extracted Text from Images:**\n"]

        for filename, text in extracted_image_text.items():
            image_sections.append(f"\n**From {filename}:**")
            image_sections.append(text)
            image_sections.append("")

        # Combine original context with image text
        enhanced_context = original_context + "\n".join(image_sections)

        logger.debug(f"Enhanced context: {len(enhanced_context)} chars total")
        return enhanced_context
