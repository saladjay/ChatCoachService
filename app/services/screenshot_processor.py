"""Screenshot processor service for analyzing chat screenshots.

This service integrates the screenshotanalysis library to perform OCR and layout
detection on chat screenshots, extracting structured conversation data.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12
"""

import logging
import os
import uuid
from typing import Optional, Tuple, List
import numpy as np
from PIL import Image
import io
import base64
import httpx

from app.models.api import ImageResult, DialogItem
from app.core.v1_config import ScreenshotConfig


logger = logging.getLogger(__name__)


# Try to import screenshotanalysis library
SCREENSHOT_ANALYSIS_AVAILABLE = False
MODELS_LOADED = False

try:
    import screenshotanalysis as AnalysisCore
    from screenshotanalysis import ChatLayoutAnalyzer, ChatTextRecognition, ChatMessageProcessor
    from screenshotanalysis.nickname_extractor import extract_nicknames_smart
    from screenshotanalysis.utils import ImageLoader
    from screenshotanalysis.dialog_pipeline2 import analyze_chat_image
    from screenshotanalysis import en_rec, layout_det, text_det
    SCREENSHOT_ANALYSIS_AVAILABLE = True
    logger.info("screenshotanalysis library imported successfully")
except ImportError as e:
    logger.error(f"Failed to import screenshotanalysis: {e}")
    AnalysisCore = None
    ChatLayoutAnalyzer = None
    ChatTextRecognition = None
    ChatMessageProcessor = None
    extract_nicknames_smart = None
    ImageLoader = None
    analyze_chat_image = None
    en_rec = None
    layout_det = None
    text_det = None


def is_url(content:str) -> bool:
    return ImageLoader._is_url(content)


class ModelUnavailableError(Exception):
    """Raised when screenshotanalysis models are not available."""
    pass


class ImageLoadError(Exception):
    """Raised when image loading fails."""
    pass


class InferenceError(Exception):
    """Raised when model inference fails."""
    pass


class ScreenshotProcessor:
    """Service for processing chat screenshots using screenshotanalysis library.
    
    This service provides:
    - Lazy loading of screenshotanalysis models
    - Image loading from URLs or base64 data
    - Text detection and layout detection
    - Text extraction using OCR
    - Speaker identification
    - Coordinate normalization to percentages
    - Message grouping by speaker
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12
    """
    
    def __init__(self, config: ScreenshotConfig):
        """Initialize the screenshot processor.
        
        Args:
            config: Screenshot processing configuration
            
        Requirements: 4.1
        """
        self.config = config
        self._models_loaded = False
        self._text_det_analyzer = None
        self._layout_det_analyzer = None
        self._text_rec_model = None
        self._message_processor = None
        
        # Check if screenshotanalysis is available
        if not SCREENSHOT_ANALYSIS_AVAILABLE:
            logger.error("screenshotanalysis library is not available")
    
    def _load_models(self) -> None:
        """Lazy load screenshotanalysis models.
        
        Loads the following models:
        - Text detection: PP-OCRv5_server_det
        - Layout detection: PP-DocLayoutV2
        - Text recognition: PP-OCRv5_server_rec
        
        Raises:
            ModelUnavailableError: If models cannot be loaded
            
        Requirements: 4.1, 4.10
        """
        if self._models_loaded:
            return
        
        if not SCREENSHOT_ANALYSIS_AVAILABLE:
            raise ModelUnavailableError(
                "screenshotanalysis library is not available. "
                "Please ensure it is installed in core/screenshotanalysis/"
            )
        
        try:
            logger.info("Loading screenshotanalysis models...")
            
            # Load text detection model
            logger.info("Loading text detection model (PP-OCRv5_server_det)...")
            if text_det is not None:
                self._text_det_analyzer = text_det
                if getattr(self._text_det_analyzer, "model", None) is None:
                    self._text_det_analyzer.load_model()
            else:
                self._text_det_analyzer = ChatLayoutAnalyzer(model_name="PP-OCRv5_server_det")
                self._text_det_analyzer.load_model()
            logger.info("Text detection model loaded")
            
            # Load layout detection model
            logger.info("Loading layout detection model (PP-DocLayoutV2)...")
            if layout_det is not None:
                self._layout_det_analyzer = layout_det
                if getattr(self._layout_det_analyzer, "model", None) is None:
                    self._layout_det_analyzer.load_model()
            else:
                self._layout_det_analyzer = ChatLayoutAnalyzer(model_name="PP-DocLayoutV2")
                self._layout_det_analyzer.load_model()
            logger.info("Layout detection model loaded")
            
            # Load text recognition model
            logger.info("Loading text recognition model (PP-OCRv5_server_rec)...")
            if en_rec is not None:
                self._text_rec_model = en_rec
                if getattr(self._text_rec_model, "model", None) is None:
                    self._text_rec_model.load_model()
            else:
                self._text_rec_model = ChatTextRecognition(model_name="PP-OCRv5_server_rec", lang="en")
                self._text_rec_model.load_model()
            logger.info("Text recognition model loaded")
            
            # Initialize message processor
            self._message_processor = ChatMessageProcessor()
            
            self._models_loaded = True
            logger.info("All screenshotanalysis models loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}", exc_info=True)
            raise ModelUnavailableError(f"Failed to load screenshotanalysis models: {str(e)}")
    
    async def _load_image_from_url(self, image_url: str) -> np.ndarray:
        """Load image from URL.
        
        Args:
            image_url: URL of the image to load
            
        Returns:
            Image as numpy array (RGB format)
            
        Raises:
            ImageLoadError: If image cannot be loaded
            
        Requirements: 4.2, 4.11
        """
        try:
            logger.info(f"Loading image from URL: {image_url}")
            
            # Download image
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = response.content
            
            # Load image using PIL
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            image_np = np.array(image)
            
            logger.info(f"Image loaded successfully: {image_np.shape}")
            return image_np
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error loading image from {image_url}: {e}")
            raise ImageLoadError(f"Failed to download image: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading image from {image_url}: {e}")
            raise ImageLoadError(f"Failed to load image: {str(e)}")
    
    def _load_image_from_base64(self, base64_data: str) -> np.ndarray:
        """Load image from base64 encoded data.
        
        Args:
            base64_data: Base64 encoded image data
            
        Returns:
            Image as numpy array (RGB format)
            
        Raises:
            ImageLoadError: If image cannot be loaded
            
        Requirements: 4.2, 4.11
        """
        try:
            logger.info("Loading image from base64 data")
            
            # Decode base64
            image_bytes = base64.b64decode(base64_data)
            
            # Load image using PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            image_np = np.array(image)
            
            logger.info(f"Image loaded successfully: {image_np.shape}")
            return image_np
            
        except Exception as e:
            logger.error(f"Error loading image from base64: {e}")
            raise ImageLoadError(f"Failed to load image from base64: {str(e)}")
    
    async def process_screenshot(
        self,
        image_url: str,
        app_type: str,
        conf_threshold: Optional[float] = None
    ) -> ImageResult:
        """Process a single screenshot and return structured dialogs.
        
        This method performs the complete screenshot processing workflow:
        1. Load models (lazy loading)
        2. Load image from URL
        3. Perform text detection
        4. Perform layout detection
        5. Extract text using OCR
        6. Identify speakers
        7. Normalize coordinates
        8. Group messages by speaker
        9. Format as DialogItem models
        
        Args:
            image_url: URL of the screenshot image
            app_type: Chat application type (e.g., "whatsapp", "telegram")
            conf_threshold: Optional confidence threshold for detection (0.0-1.0)
            
        Returns:
            ImageResult containing URL and list of DialogItem objects
            
        Raises:
            ModelUnavailableError: If models cannot be loaded
            ImageLoadError: If image cannot be loaded
            InferenceError: If model inference fails
            
        Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12
        """
        # Load models if not already loaded
        self._load_models()
        
        if analyze_chat_image is not None:
            try:
                dump_dir = os.getenv("V1_SCREENSHOT__DUMP_OUTPUT_DIR")
                output_path = None
                if isinstance(dump_dir, str) and dump_dir.strip():
                    os.makedirs(dump_dir, exist_ok=True)
                    output_path = os.path.join(dump_dir, f"dialog_{uuid.uuid4().hex}.json")

                output_payload, _ = analyze_chat_image(
                    image_path=image_url,
                    output_path=output_path,
                    draw_output_path=None,
                    text_det_analyzer=self._text_det_analyzer,
                    layout_det_analyzer=self._layout_det_analyzer,
                    text_rec=self._text_rec_model,
                    processor=self._message_processor,
                    speaker_map={"user": "self", "other": "other", "unknown": "unknown", None: "unknown"},
                    track_model_calls=False,
                )

                dialogs: list[DialogItem] = []
                for dialog_data in output_payload.get("dialogs", []):
                    dialogs.append(
                        DialogItem(
                            position=dialog_data.get("box", [0, 0, 0, 0]),
                            text=dialog_data.get("text", ""),
                            speaker=dialog_data.get("speaker", "unknown"),
                        )
                    )

                return ImageResult(
                    url=image_url,
                    dialogs=dialogs,
                )
            except Exception as e:
                logger.error(f"dialog_pipeline2 analyze_chat_image failed: {e}", exc_info=True)
                raise InferenceError(f"dialog_pipeline2 failed: {str(e)}")

        # Fallback to legacy pipeline
        image = await self._load_image_from_url(image_url)
        
        # Perform text and layout detection
        text_det_results, layout_det_results, padding, image_size = await self._detect_text_and_layout(
            image, conf_threshold
        )
        
        # Extract text and identify speakers
        dialogs = await self._extract_and_group_messages(
            image, text_det_results, layout_det_results, padding, image_size, app_type
        )
        
        return ImageResult(
            url=image_url,
            dialogs=dialogs
        )
    
    async def _detect_text_and_layout(
        self,
        image: np.ndarray,
        conf_threshold: Optional[float] = None
    ) -> Tuple:
        """Perform text detection and layout detection on the image.
        
        Args:
            image: Image as numpy array
            conf_threshold: Optional confidence threshold
            
        Returns:
            Tuple of (text_det_results, layout_det_results, padding, image_size)
            
        Raises:
            InferenceError: If detection fails
            
        Requirements: 4.3, 4.4, 4.12
        """
        try:
            logger.info("Performing text detection...")
            text_det_result = self._text_det_analyzer.analyze_chat_screenshot(image)
            
            if not text_det_result.get('success', False):
                error_msg = text_det_result.get('error', 'Unknown error')
                raise InferenceError(f"Text detection failed: {error_msg}")
            
            logger.info("Performing layout detection...")
            layout_det_result = self._layout_det_analyzer.analyze_chat_screenshot(image)
            
            if not layout_det_result.get('success', False):
                error_msg = layout_det_result.get('error', 'Unknown error')
                raise InferenceError(f"Layout detection failed: {error_msg}")
            
            # Extract results
            text_det_results = text_det_result['results']
            layout_det_results = layout_det_result['results']
            padding = text_det_result.get('padding', [0, 0, 0, 0])
            image_size = text_det_result.get('image_size', [image.shape[1], image.shape[0]])
            
            logger.info(f"Detection complete: text_det={len(text_det_results)} elements, "
                       f"layout_det={len(layout_det_results)} elements")
            
            return text_det_results, layout_det_results, padding, image_size
            
        except InferenceError:
            raise
        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
            raise InferenceError(f"Detection failed: {str(e)}")
    
    async def _extract_and_group_messages(
        self,
        image: np.ndarray,
        text_det_results: List,
        layout_det_results: List,
        padding: List[float],
        image_size: List[int],
        app_type: str
    ) -> List[DialogItem]:
        """Extract text from detected boxes and group messages by speaker.
        
        Args:
            image: Original image as numpy array
            text_det_results: Text detection results
            layout_det_results: Layout detection results
            padding: Image padding information
            image_size: Image size [width, height]
            app_type: Chat application type
            
        Returns:
            List of DialogItem objects
            
        Raises:
            InferenceError: If text extraction fails
            
        Requirements: 4.5, 4.6, 4.7, 4.8, 4.9
        """
        try:
            logger.info("Extracting text and grouping messages...")
            
            # Use message processor to format conversation
            # This handles text extraction, speaker identification, and grouping
            sorted_boxes, _ = self._message_processor.format_conversation(
                layout_det_results=layout_det_results,
                text_det_results=text_det_results,
                padding=padding,
                image_sizes=image_size,
                ratios=[1.0, 1.0],  # Default ratios
                app_type=app_type,
                use_adaptive=True,
                screen_width=image_size[0]
            )
            
            # Extract nickname if possible
            nickname = await self._extract_nickname(image, text_det_results, padding, image_size, app_type)
            
            # Convert to DialogItem objects
            dialogs = []
            current_speaker = None
            current_texts = []
            current_positions = []
            
            for box in sorted_boxes:
                # Determine speaker
                speaker = self._identify_speaker(box, nickname)
                from_user = (speaker == "self")
                
                # Normalize coordinates
                position = self._normalize_coordinates(box, padding, image_size)
                
                # Extract text from box
                text = await self._extract_text_from_box(image, box)
                
                # Group consecutive messages from same speaker
                if speaker == current_speaker and current_texts:
                    # Same speaker, add to current group
                    current_texts.append(text)
                    current_positions.append(position)
                else:
                    # Different speaker or first message, save previous group
                    if current_texts:
                        # Combine texts and use first position
                        combined_text = " ".join(current_texts)
                        dialogs.append(DialogItem(
                            position=current_positions[0],
                            text=combined_text,
                            speaker=current_speaker
                        ))
                    
                    # Start new group
                    current_speaker = speaker
                    current_texts = [text]
                    current_positions = [position]
            
            # Add final group
            if current_texts:
                combined_text = " ".join(current_texts)
                dialogs.append(DialogItem(
                    position=current_positions[0],
                    text=combined_text,
                    speaker=current_speaker
                ))
            
            logger.info(f"Extracted {len(dialogs)} dialog groups")
            return dialogs
            
        except Exception as e:
            logger.error(f"Text extraction and grouping failed: {e}", exc_info=True)
            raise InferenceError(f"Text extraction failed: {str(e)}")
    
    async def _extract_text_from_box(
        self,
        image: np.ndarray,
        box
    ) -> str:
        """Extract text from a detected text box using OCR.
        
        Args:
            image: Original image
            box: Text box object with coordinates
            
        Returns:
            Extracted text string
            
        Requirements: 4.5
        """
        try:
            # Crop image to box region
            x_min = int(box.x_min)
            y_min = int(box.y_min)
            x_max = int(box.x_max)
            y_max = int(box.y_max)
            
            # Ensure coordinates are within image bounds
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(image.shape[1], x_max)
            y_max = min(image.shape[0], y_max)
            
            text_image = image[y_min:y_max, x_min:x_max]
            
            # Use text recognition model
            result = self._text_rec_model.predict_text(text_image)
            
            # Extract text from result
            if isinstance(result, dict) and 'text' in result:
                text = result['text']
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"Failed to extract text from box: {e}")
            return ""
    
    async def _extract_nickname(
        self,
        image: np.ndarray,
        text_det_results: List,
        padding: List[float],
        image_size: List[int],
        app_type: str
    ) -> Optional[str]:
        """Extract nickname from screenshot.
        
        Args:
            image: Original image
            text_det_results: Text detection results
            padding: Image padding
            image_size: Image size
            app_type: Chat application type
            
        Returns:
            Extracted nickname or None
            
        Requirements: 4.7
        """
        try:
            if extract_nicknames_smart is None:
                return None
            
            # Use nickname extractor
            nicknames = extract_nicknames_smart(
                image,
                text_det_results,
                padding,
                image_size,
                app_type
            )
            
            if nicknames and len(nicknames) > 0:
                return nicknames[0]
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract nickname: {e}")
            return None
    
    def _identify_speaker(
        self,
        box,
        nickname: Optional[str]
    ) -> str:
        """Identify speaker for a text box.
        
        Args:
            box: Text box object
            nickname: Extracted nickname (if any)
            
        Returns:
            Speaker identifier ("self" or speaker name)
            
        Requirements: 4.6
        """
        # Check if box has speaker attribute (from adaptive detection)
        if hasattr(box, 'speaker'):
            if box.speaker == 'A':
                return "self"
            elif box.speaker == 'B':
                return nickname if nickname else "other"
            else:
                return "other"
        
        # Fallback: use position-based heuristic
        # Messages on the right are typically from self
        if hasattr(box, 'center_x'):
            # This is a simple heuristic - in production you'd use more sophisticated logic
            return "self"
        
        return "other"
    
    def _normalize_coordinates(
        self,
        box,
        padding: List[float],
        image_size: List[int]
    ) -> List[float]:
        """Normalize pixel coordinates to percentages (0.0-1.0).
        
        Args:
            box: Text box with pixel coordinates
            padding: Image padding [top, right, bottom, left]
            image_size: Image size [width, height]
            
        Returns:
            Normalized coordinates [min_x, min_y, max_x, max_y] in range 0.0-1.0
            
        Requirements: 4.8
        """
        # Get image dimensions
        width, height = image_size
        
        # Adjust for padding
        pad_top, pad_right, pad_bottom, pad_left = padding
        effective_width = width - pad_left - pad_right
        effective_height = height - pad_top - pad_bottom
        
        # Get box coordinates
        x_min = box.x_min - pad_left
        y_min = box.y_min - pad_top
        x_max = box.x_max - pad_left
        y_max = box.y_max - pad_top
        
        # Normalize to 0.0-1.0 range
        norm_x_min = max(0.0, min(1.0, x_min / effective_width))
        norm_y_min = max(0.0, min(1.0, y_min / effective_height))
        norm_x_max = max(0.0, min(1.0, x_max / effective_width))
        norm_y_max = max(0.0, min(1.0, y_max / effective_height))
        
        return [norm_x_min, norm_y_min, norm_x_max, norm_y_max]
