#!/usr/bin/env python3
"""Verify OCR runtime (run inside Docker container or local venv with Tesseract/Poppler)."""

import sys
from pathlib import Path

# backend/ on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ocr_runtime import apply_runtime_configuration, build_ocr_status_payload


def main() -> int:
    apply_runtime_configuration()
    payload = build_ocr_status_payload()
    print("OCR status:")
    print(f"  ocr_ready={payload['ocr_ready']}")
    print(f"  tesseract_binary={payload['tesseract_binary']}")
    print(f"  poppler_available={payload['poppler_available']}")
    print(f"  tesseract_path={payload.get('tesseract_path')}")
    print(f"  poppler_path={payload.get('poppler_path')}")
    notes = payload.get("dependencies", {}).get("notes", [])
    if notes:
        print("  notes:")
        for note in notes:
            print(f"    - {note}")
    return 0 if payload["ocr_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
