"""
CareLens Overlay Renderer.
Converts normalized coordinates [ymin, xmin, ymax, xmax] (0..1000) to display pixel boxes,
and annotates images for headless audits or exported reports.
"""

from typing import List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from app.schema.contract import VisualOverlay, OverlayStatus


class OverlayRenderer:
    COLOR_PASS = {
        "stroke": "#10b981",       # Emerald 500
        "fill": "rgba(16, 185, 129, 0.18)",
        "rgb": (16, 185, 129),
    }
    COLOR_FAIL = {
        "stroke": "#ef4444",       # Rose 500
        "fill": "rgba(239, 68, 68, 0.25)",
        "rgb": (239, 68, 68),
    }

    @classmethod
    def denormalize_box(
        cls,
        box_2d: List[int],
        canvas_width: int,
        canvas_height: int,
    ) -> Dict[str, int]:
        """
        Converts normalized [ymin, xmin, ymax, xmax] (0..1000)
        to canvas pixel bounding rectangle: x, y, width, height.
        """
        ymin, xmin, ymax, xmax = box_2d
        x = int((xmin / 1000.0) * canvas_width)
        y = int((ymin / 1000.0) * canvas_height)
        w = max(1, int(((xmax - xmin) / 1000.0) * canvas_width))
        h = max(1, int(((ymax - ymin) / 1000.0) * canvas_height))

        return {
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "xmin_px": x,
            "ymin_px": y,
            "xmax_px": x + w,
            "ymax_px": y + h,
        }

    @classmethod
    def format_overlays_for_canvas(
        cls,
        overlays: List[VisualOverlay],
        canvas_width: int,
        canvas_height: int,
    ) -> List[Dict[str, Any]]:
        """
        Returns display-ready overlay structures for frontend canvas or SVG rendering.
        """
        rendered = []
        for i, ov in enumerate(overlays):
            px_box = cls.denormalize_box(ov.box_2d, canvas_width, canvas_height)
            color_scheme = cls.COLOR_FAIL if ov.status == OverlayStatus.FAIL else cls.COLOR_PASS
            rendered.append({
                "id": f"overlay_{i}",
                "label": ov.label,
                "status": ov.status.value,
                "detail": ov.detail,
                "normalized_box": ov.box_2d,
                "pixel_box": px_box,
                "stroke_color": color_scheme["stroke"],
                "fill_color": color_scheme["fill"],
            })
        return rendered

    @classmethod
    def annotate_pil_image(
        cls,
        image: Image.Image,
        overlays: List[VisualOverlay],
    ) -> Image.Image:
        """
        Draws bounding boxes and labels onto a PIL image for server-side verification.
        """
        annotated = image.copy().convert("RGB")
        draw = ImageDraw.Draw(annotated)
        w, h = annotated.size

        for ov in overlays:
            px = cls.denormalize_box(ov.box_2d, w, h)
            color = cls.COLOR_FAIL["rgb"] if ov.status == OverlayStatus.FAIL else cls.COLOR_PASS["rgb"]
            draw.rectangle(
                [px["xmin_px"], px["ymin_px"], px["xmax_px"], px["ymax_px"]],
                outline=color,
                width=3,
            )
            # Label banner
            banner_text = f"{ov.label} [{ov.status.value}]"
            draw.rectangle(
                [px["xmin_px"], max(0, px["ymin_px"] - 18), px["xmin_px"] + len(banner_text) * 8, px["ymin_px"]],
                fill=color,
            )
            draw.text(
                (px["xmin_px"] + 4, max(0, px["ymin_px"] - 16)),
                banner_text,
                fill=(255, 255, 255),
            )

        return annotated
