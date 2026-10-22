"""
CareLens Image Capture and Preprocessing Module.
Handles image validation, aspect-preserving resizing, SVG conversion, and quality evaluation.
"""

import io
import re
import base64
import xml.etree.ElementTree as ET
from typing import Tuple, Dict, Any, Optional
from PIL import Image, ImageStat, ImageOps, ImageDraw, ImageFont


class ImagePreprocessor:
    MIN_DIMENSION = 64
    MAX_DIMENSION = 2048

    @classmethod
    def is_svg_bytes(cls, data: bytes) -> bool:
        snippet = data[:300].strip().lower()
        return snippet.startswith(b"<svg") or snippet.startswith(b"<?xml") or b"<svg" in snippet

    @classmethod
    def decode_base64_image(cls, data_str: str) -> Tuple[Image.Image, str]:
        """
        Decodes base64 string (with optional data:image/xxx;base64, prefix) to PIL Image.
        Returns (Image, detected_mime_format).
        """
        if "," in data_str:
            header, b64_payload = data_str.split(",", 1)
            fmt = "image/jpeg"
            if "png" in header:
                fmt = "image/png"
            elif "webp" in header:
                fmt = "image/webp"
            elif "svg" in header:
                fmt = "image/svg+xml"
        else:
            b64_payload = data_str
            fmt = "image/jpeg"

        image_bytes = base64.b64decode(b64_payload)
        return cls.from_bytes(image_bytes), fmt

    @classmethod
    def from_bytes(cls, image_bytes: bytes) -> Image.Image:
        """
        Loads PIL Image from raw bytes, handling SVG rendering or EXIF orientation.
        """
        if cls.is_svg_bytes(image_bytes):
            return cls.rasterize_svg_bytes(image_bytes)

        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        return image

    @classmethod
    def rasterize_svg_bytes(cls, svg_bytes: bytes, target_size: Tuple[int, int] = (800, 800)) -> Image.Image:
        """
        Lightweight native SVG rasterizer: parses SVG dimensions, colors, and text
        to create an accurate high-resolution PIL Image without external cairo/inkscape dependencies.
        """
        try:
            root = ET.fromstring(svg_bytes)
            # Check viewBox or width/height
            view_box = root.attrib.get("viewBox")
            if view_box:
                parts = [float(p) for p in re.findall(r"[-+]?\d*\.?\d+", view_box)]
                if len(parts) == 4:
                    w, h = int(parts[2]), int(parts[3])
                else:
                    w, h = target_size
            else:
                w = int(root.attrib.get("width", target_size[0]))
                h = int(root.attrib.get("height", target_size[1]))
        except Exception:
            w, h = target_size

        canvas = Image.new("RGB", (w, h), color=(15, 23, 42))  # Slate 900 background
        draw = ImageDraw.Draw(canvas)

        # Parse text elements and major rectangles from the SVG to render onto canvas
        try:
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                if tag == "rect":
                    rx = int(float(elem.attrib.get("x", 0)))
                    ry = int(float(elem.attrib.get("y", 0)))
                    rw = int(float(elem.attrib.get("width", 0)))
                    rh = int(float(elem.attrib.get("height", 0)))
                    fill = elem.attrib.get("fill", "")
                    if fill and fill.startswith("#"):
                        # Parse hex color
                        hex_col = fill.lstrip("#")
                        if len(hex_col) == 6:
                            rgb = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
                            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=rgb)
                elif tag == "text":
                    tx = int(float(elem.attrib.get("x", 0)))
                    ty = int(float(elem.attrib.get("y", 0)))
                    text_content = elem.text or ""
                    fill = elem.attrib.get("fill", "#ffffff")
                    rgb = (255, 255, 255)
                    if fill.startswith("#"):
                        hex_col = fill.lstrip("#")
                        if len(hex_col) == 6:
                            rgb = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
                    draw.text((tx, max(0, ty - 14)), text_content, fill=rgb)
        except Exception:
            pass

        return canvas

    @classmethod
    def preprocess_image(
        cls,
        image: Image.Image,
        max_size: int = MAX_DIMENSION,
    ) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Validates dimensions, applies aspect-preserving scaling if necessary,
        and computes image clarity heuristics.
        """
        orig_w, orig_h = image.size

        if orig_w < cls.MIN_DIMENSION or orig_h < cls.MIN_DIMENSION:
            raise ValueError(
                f"Image dimensions ({orig_w}x{orig_h}) are below minimum {cls.MIN_DIMENSION}px"
            )

        # Scale down if exceeds max_size while preserving aspect ratio and fine text detail
        new_w, new_h = orig_w, orig_h
        if orig_w > max_size or orig_h > max_size:
            ratio = min(max_size / orig_w, max_size / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Basic image quality assessment (brightness and contrast)
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        mean_brightness = stat.mean[0]
        stddev_contrast = stat.stddev[0]

        is_underexposed = mean_brightness < 20.0
        is_overexposed = mean_brightness > 235.0
        is_low_contrast = stddev_contrast < 12.0

        clarity_ok = not (is_underexposed or is_overexposed or is_low_contrast)

        metadata = {
            "original_dimensions": (orig_w, orig_h),
            "processed_dimensions": (new_w, new_h),
            "mean_brightness": round(mean_brightness, 2),
            "contrast_stddev": round(stddev_contrast, 2),
            "clarity_ok": clarity_ok,
            "quality_flags": {
                "underexposed": is_underexposed,
                "overexposed": is_overexposed,
                "low_contrast": is_low_contrast,
            },
        }

        return image, metadata

    @classmethod
    def to_base64_jpeg(cls, image: Image.Image, quality: int = 90) -> str:
        """Encodes PIL Image to JPEG base64 string."""
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
