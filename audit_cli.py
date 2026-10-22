#!/usr/bin/env python3
"""
CareLens Command Line Interface (CLI).
Provides command-line clinical visual safety auditing, testing, and report generation.
"""

import os
import sys
import json
import base64
import argparse
from typing import Optional

from app.schema.contract import CareLensResponse
from app.inference.edge_engine import EdgeClinicalEngine
from app.presets import PRESET_SCENARIOS
from app.protocol_engine.protocols import CLINICAL_PROTOCOLS


def encode_file_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="CareLens CLI - Edge-Native Clinical Visual Safety Auditor"
    )
    parser.add_argument("--image", type=str, help="Path to input image file (JPEG, PNG, SVG)")
    parser.add_argument("--preset", type=str, choices=list(PRESET_SCENARIOS.keys()), help="Run audit on a standard clinical preset")
    parser.add_argument("--protocol", type=str, default="adult_icu_v1.0", choices=list(CLINICAL_PROTOCOLS.keys()), help="Versioned protocol ID")
    parser.add_argument("--patient", type=str, default="adult", choices=["adult", "pediatric", "neonatal"], help="Patient clinical context")
    parser.add_argument("--backend", type=str, default="auto", choices=["auto", "gemma4", "edge"], help="Inference backend")
    parser.add_argument("--json", action="store_true", help="Output pure canonical JSON contract")

    args = parser.parse_args()

    if not args.image and not args.preset:
        parser.print_help()
        print("\nError: Please provide either --image <path> or --preset <name>.")
        sys.exit(1)

    engine = EdgeClinicalEngine()
    image_b64 = None
    preset_hint = None
    protocol_id = args.protocol
    patient_context = args.patient

    if args.preset:
        preset_info = PRESET_SCENARIOS[args.preset]
        preset_hint = args.preset
        protocol_id = preset_info.get("protocol_id", protocol_id)
        patient_context = preset_info.get("patient_context", patient_context)
        # Load asset file
        asset_rel = preset_info["asset_url"].lstrip("/")
        asset_path = os.path.join(os.path.dirname(__file__), "frontend", asset_rel)
        if os.path.exists(asset_path):
            image_b64 = encode_file_to_b64(asset_path)
        else:
            # Create a simple placeholder image for the preset
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (600, 600), color=(15, 23, 42))
            draw = ImageDraw.Draw(img)
            draw.text((50, 50), f"Preset: {args.preset}", fill=(56, 189, 248))
            import io
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    elif args.image:
        if not os.path.exists(args.image):
            print(f"Error: Image file not found: {args.image}")
            sys.exit(1)
        image_b64 = encode_file_to_b64(args.image)

    # Execute audit
    response, meta = engine.audit(
        image_b64=image_b64,
        protocol_id=protocol_id,
        patient_context=patient_context,
        preferred_backend=args.backend,
        preset_hint=preset_hint,
    )

    if args.json:
        # Output exact canonical contract without markdown
        print(response.model_dump_json(indent=2))
        return

    # Formatted terminal display
    status = response.overall_status.value
    status_color = "\033[92m" if status == "PASS" else ("\033[93m" if status == "WARNING" else "\033[91m")
    reset_color = "\033[0m"

    print("\n" + "=" * 65)
    print(f"  CARELENS CLINICAL VISUAL SAFETY AUDIT REPORT")
    print("=" * 65)
    print(f" Audit ID:       {meta['audit_id']}")
    print(f" Timestamp:      {meta['timestamp']}")
    print(f" Latency:        {meta['latency_ms']} ms")
    print(f" Provider:       {meta['provider']}")
    print(f" Protocol:       {meta['protocol_id']} (v{meta['protocol_version']})")
    print(f" Patient:        {meta['patient_context']}")
    print(f" Status:         {status_color}{status}{reset_color}")
    print(f" Inspection:     {response.inspection_type.value}")
    print("-" * 65)

    print(" Extracted Vitals:")
    v = response.vitals_extracted
    print(f"   • Heart Rate:       {v.heart_rate_bpm} bpm")
    print(f"   • SpO2:             {v.spo2_percent} %")
    print(f"   • Blood Pressure:   {v.blood_pressure_mmHg} mmHg")
    print(f"   • Respiration:      {v.respiration_rate} breaths/min")

    print("\n Visual Overlays:")
    if not response.visual_overlays:
        print("   (None detected)")
    for ov in response.visual_overlays:
        st_color = "\033[92m" if ov.status.value == "PASS" else "\033[91m"
        print(f"   • [{st_color}{ov.status.value}{reset_color}] {ov.label}")
        print(f"     Box (ymin, xmin, ymax, xmax): {ov.box_2d}")
        print(f"     Detail: {ov.detail}")

    print("\n Findings:")
    for f in response.findings:
        print(f"   • {f}")

    print(f"\n Voice Alert:    \"{response.audio_alert_text}\"")
    print("=" * 65)
    print(f" DISCLAIMER: {meta['disclaimer']}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
