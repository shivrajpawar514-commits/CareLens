"""
CareLens Image Preprocessor and Ingestion Tests.
Validates base64 decoding, dimension validation, aspect-preserving resizing, and quality evaluation.
"""

import io
import unittest
from PIL import Image
from app.capture.preprocessor import ImagePreprocessor


class TestImagePreprocessor(unittest.TestCase):
    def test_decode_valid_image(self):
        """Test base64 decoding and dimension verification."""
        img = Image.new("RGB", (200, 200), color=(120, 180, 220))
        b64 = ImagePreprocessor.to_base64_jpeg(img)
        decoded, fmt = ImagePreprocessor.decode_base64_image(b64)
        self.assertEqual(decoded.size, (200, 200))
        self.assertEqual(fmt, "image/jpeg")

    def test_aspect_preserving_scaling(self):
        """Ensure scaling preserves aspect ratio when exceeding max dimension."""
        img = Image.new("RGB", (3000, 1500), color=(50, 50, 50))
        processed, meta = ImagePreprocessor.preprocess_image(img, max_size=1000)
        w, h = processed.size
        self.assertLessEqual(w, 1000)
        self.assertLessEqual(h, 1000)
        # Ratio should still be 2:1
        self.assertAlmostEqual(w / h, 2.0, places=1)

    def test_reject_undersized_image(self):
        """Images below 64px cannot reliably display dials or text and should be rejected."""
        tiny = Image.new("RGB", (32, 32), color=(0, 0, 0))
        with self.assertRaises(ValueError):
            ImagePreprocessor.preprocess_image(tiny)

    def test_quality_clarity_detection(self):
        """Detect extreme underexposure or low contrast."""
        # Extremely dark image (mean brightness < 10)
        dark_img = Image.new("RGB", (200, 200), color=(5, 5, 5))
        _, meta = ImagePreprocessor.preprocess_image(dark_img)
        self.assertFalse(meta["clarity_ok"])
        self.assertTrue(meta["quality_flags"]["underexposed"])


if __name__ == "__main__":
    unittest.main()
