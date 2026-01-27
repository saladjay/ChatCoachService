"""Property-based tests for Image Fetcher component.

Tests:
- Property 1: Image Download and Dimension Extraction
- Property 14: URL Format Validation
- Property 15: Base64 Conversion

Validates: Requirements 1.1, 5.1, 5.2, 5.3, 5.4
"""

import base64
import io
import pytest
from hypothesis import given, settings, strategies as st
from PIL import Image

from app.services.image_fetcher import ImageFetcher


# Strategies for generating test data

# Valid URL components
valid_schemes = st.sampled_from(["http", "https"])
valid_domains = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-"),
    min_size=3,
    max_size=50,
).filter(lambda x: len(x.strip()) > 0 and not x.startswith(".") and not x.endswith("."))

valid_paths = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="/-_."),
    min_size=0,
    max_size=100,
)

# Invalid URL components
invalid_schemes = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=1,
    max_size=10,
).filter(lambda x: x not in ["http", "https"])

# Strategy for valid URLs
@st.composite
def valid_url_strategy(draw):
    """Generate valid HTTP/HTTPS URLs."""
    scheme = draw(valid_schemes)
    domain = draw(valid_domains)
    path = draw(valid_paths)
    
    if path and not path.startswith("/"):
        path = "/" + path
    
    return f"{scheme}://{domain}{path}"


# Strategy for invalid URLs (wrong scheme)
@st.composite
def invalid_scheme_url_strategy(draw):
    """Generate URLs with invalid schemes (not HTTP/HTTPS)."""
    scheme = draw(invalid_schemes)
    domain = draw(valid_domains)
    path = draw(valid_paths)
    
    if path and not path.startswith("/"):
        path = "/" + path
    
    return f"{scheme}://{domain}{path}"


# Strategy for URLs without domain
@st.composite
def no_domain_url_strategy(draw):
    """Generate URLs without domain."""
    scheme = draw(valid_schemes)
    path = draw(valid_paths)
    
    if path and not path.startswith("/"):
        path = "/" + path
    
    return f"{scheme}://{path}"


class TestURLFormatValidation:
    """
    Property 14: URL Format Validation
    
    *For any* image URL provided, the Image_Fetcher should validate that it is
    a properly formatted HTTP/HTTPS URL before attempting download.
    
    **Feature: chat-screenshot-parser, Property 14: URL Format Validation**
    **Validates: Requirements 5.1**
    """
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(url=valid_url_strategy())
    async def test_valid_http_https_urls_pass_validation(self, url: str):
        """
        Property 14: Valid HTTP/HTTPS URLs should pass validation
        
        For any properly formatted HTTP or HTTPS URL, the _validate_url method
        should not raise an exception.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should not raise ValueError
        try:
            fetcher._validate_url(url)
        except ValueError as e:
            pytest.fail(f"Valid URL '{url}' failed validation: {e}")
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(url=invalid_scheme_url_strategy())
    async def test_non_http_https_urls_fail_validation(self, url: str):
        """
        Property 14: Non-HTTP/HTTPS URLs should fail validation
        
        For any URL with a scheme other than HTTP or HTTPS, the _validate_url
        method should raise a ValueError.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            fetcher._validate_url(url)
        
        # Verify error message mentions protocol/scheme
        assert "protocol" in str(exc_info.value).lower() or "scheme" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(url=no_domain_url_strategy())
    async def test_urls_without_domain_fail_validation(self, url: str):
        """
        Property 14: URLs without domain should fail validation
        
        For any URL missing a domain name, the _validate_url method should
        raise a ValueError.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            fetcher._validate_url(url)
        
        # Verify error message mentions domain
        assert "domain" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        invalid_input=st.one_of(
            st.none(),
            st.integers(),
            st.floats(),
            st.lists(st.text()),
            st.dictionaries(st.text(), st.text()),
        )
    )
    async def test_non_string_urls_fail_validation(self, invalid_input):
        """
        Property 14: Non-string inputs should fail validation
        
        For any input that is not a string, the _validate_url method should
        raise a ValueError.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            fetcher._validate_url(invalid_input)
        
        # Verify error message mentions string requirement
        assert "string" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        whitespace=st.text(
            alphabet=st.characters(categories=(), include_characters=" \t\n\r"),
            min_size=0,
            max_size=10,
        )
    )
    async def test_empty_or_whitespace_urls_fail_validation(self, whitespace: str):
        """
        Property 14: Empty or whitespace-only URLs should fail validation
        
        For any empty string or whitespace-only string, the _validate_url
        method should raise a ValueError.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError (any validation error is acceptable)
        with pytest.raises(ValueError):
            fetcher._validate_url(whitespace)
    
    @pytest.mark.asyncio
    @settings(max_examples=100)
    @given(
        malformed=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" !@#$%^&*()"),
            min_size=1,
            max_size=50,
        ).filter(lambda x: "://" not in x)
    )
    async def test_malformed_urls_fail_validation(self, malformed: str):
        """
        Property 14: Malformed URLs should fail validation
        
        For any string that doesn't follow URL format (no ://), the _validate_url
        method should raise a ValueError.
        
        **Validates: Requirements 5.1**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError
        with pytest.raises(ValueError):
            fetcher._validate_url(malformed)


class TestImageDimensionExtraction:
    """
    Property 1: Image Download and Dimension Extraction
    
    *For any* valid image URL, when the Image_Fetcher downloads the image,
    it should successfully extract positive integer values for width and height.
    
    **Feature: chat-screenshot-parser, Property 1: Image Download and Dimension Extraction**
    **Validates: Requirements 1.1, 5.2, 5.3**
    """
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
        format=st.sampled_from(["PNG", "JPEG", "WEBP"]),
    )
    def test_dimension_extraction_returns_positive_integers(
        self, width: int, height: int, format: str
    ):
        """
        Property 1: Dimension extraction returns positive integers
        
        For any valid image with positive dimensions, the _extract_dimensions
        method should return the correct width and height as positive integers.
        
        **Validates: Requirements 1.1, 5.2, 5.3**
        """
        fetcher = ImageFetcher()
        
        # Create a test image with specified dimensions
        img = Image.new("RGB", (width, height), color="white")
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        image_bytes = img_bytes.getvalue()
        
        # Extract dimensions
        extracted_width, extracted_height = fetcher._extract_dimensions(image_bytes)
        
        # Verify dimensions match and are positive integers
        assert isinstance(extracted_width, int), f"Width should be int, got {type(extracted_width)}"
        assert isinstance(extracted_height, int), f"Height should be int, got {type(extracted_height)}"
        assert extracted_width > 0, f"Width should be positive, got {extracted_width}"
        assert extracted_height > 0, f"Height should be positive, got {extracted_height}"
        assert extracted_width == width, f"Expected width {width}, got {extracted_width}"
        assert extracted_height == height, f"Expected height {height}, got {extracted_height}"
    
    @settings(max_examples=100, deadline=500)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
    )
    def test_dimension_extraction_supports_png_format(self, width: int, height: int):
        """
        Property 1: PNG format is supported
        
        For any valid PNG image, the _extract_dimensions method should
        successfully extract dimensions without raising an error.
        
        **Validates: Requirements 5.3, 5.7**
        """
        fetcher = ImageFetcher()
        
        # Create PNG image
        img = Image.new("RGB", (width, height), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_bytes = img_bytes.getvalue()
        
        # Should not raise an exception
        extracted_width, extracted_height = fetcher._extract_dimensions(image_bytes)
        assert extracted_width == width
        assert extracted_height == height
    
    @settings(max_examples=100, deadline=500)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
    )
    def test_dimension_extraction_supports_jpeg_format(self, width: int, height: int):
        """
        Property 1: JPEG format is supported
        
        For any valid JPEG image, the _extract_dimensions method should
        successfully extract dimensions without raising an error.
        
        **Validates: Requirements 5.3, 5.7**
        """
        fetcher = ImageFetcher()
        
        # Create JPEG image
        img = Image.new("RGB", (width, height), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        image_bytes = img_bytes.getvalue()
        
        # Should not raise an exception
        extracted_width, extracted_height = fetcher._extract_dimensions(image_bytes)
        assert extracted_width == width
        assert extracted_height == height
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
    )
    def test_dimension_extraction_supports_webp_format(self, width: int, height: int):
        """
        Property 1: WebP format is supported
        
        For any valid WebP image, the _extract_dimensions method should
        successfully extract dimensions without raising an error.
        
        **Validates: Requirements 5.3, 5.7**
        """
        fetcher = ImageFetcher()
        
        # Create WebP image
        img = Image.new("RGB", (width, height), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="WEBP")
        image_bytes = img_bytes.getvalue()
        
        # Should not raise an exception
        extracted_width, extracted_height = fetcher._extract_dimensions(image_bytes)
        assert extracted_width == width
        assert extracted_height == height
    
    @settings(max_examples=100)
    @given(
        invalid_data=st.one_of(
            st.binary(min_size=0, max_size=0),  # Empty bytes
            st.binary(min_size=1, max_size=100).filter(
                lambda x: not x.startswith(b"\x89PNG") and not x.startswith(b"\xff\xd8")
            ),  # Invalid image data
        )
    )
    def test_dimension_extraction_fails_on_invalid_data(self, invalid_data: bytes):
        """
        Property 1: Invalid image data raises ValueError
        
        For any invalid or empty image data, the _extract_dimensions method
        should raise a ValueError.
        
        **Validates: Requirements 5.6**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError
        with pytest.raises(ValueError):
            fetcher._extract_dimensions(invalid_data)
    
    @settings(max_examples=50)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
    )
    def test_dimension_extraction_rejects_unsupported_formats(
        self, width: int, height: int
    ):
        """
        Property 1: Unsupported formats raise ValueError
        
        For any image in an unsupported format (e.g., BMP, GIF), the
        _extract_dimensions method should raise a ValueError.
        
        **Validates: Requirements 5.7**
        """
        fetcher = ImageFetcher()
        
        # Create BMP image (unsupported format)
        img = Image.new("RGB", (width, height), color="yellow")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="BMP")
        image_bytes = img_bytes.getvalue()
        
        # Should raise ValueError for unsupported format
        with pytest.raises(ValueError) as exc_info:
            fetcher._extract_dimensions(image_bytes)
        
        # Verify error message mentions format
        assert "format" in str(exc_info.value).lower()




class TestBase64Conversion:
    """
    Property 15: Base64 Conversion
    
    *For any* successfully downloaded image, the Image_Fetcher should convert
    it to valid base64-encoded string format.
    
    **Feature: chat-screenshot-parser, Property 15: Base64 Conversion**
    **Validates: Requirements 5.4**
    """
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
        format=st.sampled_from(["PNG", "JPEG", "WEBP"]),
    )
    def test_base64_conversion_produces_valid_base64_string(
        self, width: int, height: int, format: str
    ):
        """
        Property 15: Base64 conversion produces valid base64 string
        
        For any valid image bytes, the _convert_to_base64 method should return
        a valid base64-encoded string that can be decoded back to the original bytes.
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Create a test image with specified dimensions
        img = Image.new("RGB", (width, height), color="white")
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        image_bytes = img_bytes.getvalue()
        
        # Convert to base64
        base64_string = fetcher._convert_to_base64(image_bytes)
        
        # Verify it's a string
        assert isinstance(base64_string, str), f"Base64 output should be str, got {type(base64_string)}"
        
        # Verify it's not empty
        assert len(base64_string) > 0, "Base64 string should not be empty"
        
        # Verify it's valid base64 by decoding it
        try:
            decoded_bytes = base64.b64decode(base64_string)
        except Exception as e:
            pytest.fail(f"Failed to decode base64 string: {e}")
        
        # Verify round-trip: decoded bytes should match original
        assert decoded_bytes == image_bytes, "Round-trip conversion should preserve original bytes"
    
    @settings(max_examples=100, deadline=1000)
    @given(
        data=st.binary(min_size=1, max_size=10000)
    )
    def test_base64_conversion_round_trip_property(self, data: bytes):
        """
        Property 15: Base64 round-trip preserves data
        
        For any arbitrary bytes, converting to base64 and back should preserve
        the original data (round-trip property).
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Convert to base64
        base64_string = fetcher._convert_to_base64(data)
        
        # Decode back to bytes
        decoded_bytes = base64.b64decode(base64_string)
        
        # Verify round-trip preserves data
        assert decoded_bytes == data, "Round-trip conversion should preserve original data"
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
        format=st.sampled_from(["PNG", "JPEG", "WEBP"]),
    )
    def test_base64_string_contains_only_valid_characters(
        self, width: int, height: int, format: str
    ):
        """
        Property 15: Base64 string contains only valid base64 characters
        
        For any image, the base64 string should only contain characters from
        the base64 alphabet (A-Z, a-z, 0-9, +, /, =).
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Create a test image
        img = Image.new("RGB", (width, height), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        image_bytes = img_bytes.getvalue()
        
        # Convert to base64
        base64_string = fetcher._convert_to_base64(image_bytes)
        
        # Verify all characters are valid base64 characters
        valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
        for char in base64_string:
            assert char in valid_chars, f"Invalid base64 character: {char}"
    
    def test_base64_conversion_fails_on_empty_data(self):
        """
        Property 15: Empty data raises ValueError
        
        For empty bytes, the _convert_to_base64 method should raise a ValueError.
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Should raise ValueError for empty data
        with pytest.raises(ValueError) as exc_info:
            fetcher._convert_to_base64(b"")
        
        # Verify error message mentions empty data
        assert "empty" in str(exc_info.value).lower()
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
    )
    def test_base64_length_is_predictable(self, width: int, height: int):
        """
        Property 15: Base64 length follows mathematical relationship
        
        For any data, the base64 string length should be approximately
        (4 * ceil(len(data) / 3)), following the base64 encoding formula.
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Create a test image
        img = Image.new("RGB", (width, height), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        image_bytes = img_bytes.getvalue()
        
        # Convert to base64
        base64_string = fetcher._convert_to_base64(image_bytes)
        
        # Calculate expected length (base64 encoding formula)
        import math
        expected_length = 4 * math.ceil(len(image_bytes) / 3)
        
        # Verify length matches expected (allowing for padding)
        assert len(base64_string) == expected_length, (
            f"Base64 length {len(base64_string)} doesn't match expected {expected_length}"
        )
    
    @settings(max_examples=100, deadline=1000)
    @given(
        width=st.integers(min_value=1, max_value=2048),
        height=st.integers(min_value=1, max_value=2048),
        format=st.sampled_from(["PNG", "JPEG", "WEBP"]),
    )
    def test_base64_conversion_is_deterministic(
        self, width: int, height: int, format: str
    ):
        """
        Property 15: Base64 conversion is deterministic
        
        For any image bytes, converting to base64 multiple times should
        produce the same result (deterministic property).
        
        **Validates: Requirements 5.4**
        """
        fetcher = ImageFetcher()
        
        # Create a test image
        img = Image.new("RGB", (width, height), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format=format)
        image_bytes = img_bytes.getvalue()
        
        # Convert to base64 multiple times
        base64_string_1 = fetcher._convert_to_base64(image_bytes)
        base64_string_2 = fetcher._convert_to_base64(image_bytes)
        base64_string_3 = fetcher._convert_to_base64(image_bytes)
        
        # Verify all conversions produce the same result
        assert base64_string_1 == base64_string_2, "Base64 conversion should be deterministic"
        assert base64_string_2 == base64_string_3, "Base64 conversion should be deterministic"
