"""
Parse uploaded files (CSV, XLSX, JSON, XML, PDF, TXT, images) into pandas DataFrames.
Auto-detect format and inferred source/department type.
"""

import json
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from app.core.logging_config import get_logger
from app.services.header_canonicalization import canonicalize_columns

logger = get_logger("gpip.file_ingestion")

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".pdf",
    ".txt",
    ".json",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
}


def detect_file_format(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in {".xls", ".xlsx"}:
        return "xlsx"
    if ext == ".csv":
        return "csv"
    if ext == ".json":
        return "json"
    if ext == ".xml":
        return "xml"
    if ext == ".pdf":
        return "pdf"
    if ext == ".txt":
        return "txt"
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    return "unknown"


def detect_source_type(filename: str, columns: List[str]) -> str:
    """Heuristic source/department detection from filename + headers."""
    blob = f"{filename} {' '.join(str(c) for c in columns)}".lower()
    rules = [
        ("welfare", ["welfare", "scheme", "beneficiary", "ration", "pension"]),
        ("telecom", ["telecom", "mobile", "subscriber", "msisdn", "customer_record"]),
        ("utility", ["utility", "electricity", "gas", "water", "consumer", "meter", "connection"]),
        ("employee", ["employee", "payroll", "staff", "personnel", "department"]),
        ("bank", ["bank", "account", "ifsc", "branch", "transaction"]),
    ]
    for source, keywords in rules:
        if any(k in blob for k in keywords):
            return source
    return "general"


def _records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def _flatten_xml_element(element: ET.Element, prefix: str = "") -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    key = f"{prefix}{tag}" if not prefix else f"{prefix}_{tag}"
    if element.text and element.text.strip():
        row[key] = element.text.strip()
    for child in element:
        child_row = _flatten_xml_element(child, key)
        row.update(child_row)
    return row


def parse_csv(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)


def parse_xlsx(file_path: str) -> pd.DataFrame:
    ext = Path(file_path).suffix.lower()
    if ext == ".xlsx":
        return pd.read_excel(file_path, engine="openpyxl")
    return pd.read_excel(file_path)


def _ocr_result_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    table_rows = result.get("table_rows") or []
    if table_rows:
        max_cols = max(len(r) for r in table_rows)
        cols = [f"col_{i + 1}" for i in range(max_cols)]
        padded = [r + [""] * (max_cols - len(r)) for r in table_rows]
        return pd.DataFrame(padded, columns=cols)
    text = result.get("extracted_text") or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines:
        return pd.DataFrame({"text_line": lines})
    return pd.DataFrame([{"raw_content": text or "[No text extracted]"}])


def parse_txt(file_path: str) -> pd.DataFrame:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if not content.strip():
        return pd.DataFrame()

    sample_lines = content.splitlines()[:5]
    for sep in (",", "\t", "|", ";"):
        if any(sep in line for line in sample_lines):
            try:
                df = pd.read_csv(StringIO(content), sep=sep)
                if len(df.columns) > 1 and len(df) > 0:
                    return df
            except Exception:
                continue

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if lines:
        return pd.DataFrame({"text_line": lines})
    return pd.DataFrame([{"raw_content": content}])


def parse_json(file_path: str) -> pd.DataFrame:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    if isinstance(data, list):
        return _records_to_dataframe(data)
    if isinstance(data, dict):
        for key in ("records", "data", "items", "rows", "results"):
            if isinstance(data.get(key), list):
                return _records_to_dataframe(data[key])
        return _records_to_dataframe([data])
    return pd.DataFrame()


def parse_xml(file_path: str) -> pd.DataFrame:
    tree = ET.parse(file_path)
    root = tree.getroot()
    rows: List[Dict[str, Any]] = []
    # Prefer repeated child records under root
    children = list(root)
    if children:
        for child in children:
            rows.append(_flatten_xml_element(child))
    else:
        rows.append(_flatten_xml_element(root))
    return _records_to_dataframe(rows)


def parse_pdf(file_path: str, filename: str) -> pd.DataFrame:
    try:
        from app.services.ocr_service import process_file_ocr

        result = process_file_ocr(file_path, filename)
        return _ocr_result_to_dataframe(result)
    except Exception as exc:
        logger.warning("PDF OCR parse failed for %s: %s", filename, exc)
        return pd.DataFrame(
            [
                {
                    "raw_content": f"[PDF stored for manual review — OCR unavailable: {filename}]",
                    "source_file": filename,
                }
            ]
        )


def parse_image(file_path: str, filename: str) -> pd.DataFrame:
    try:
        from app.services.ocr_service import process_file_ocr

        result = process_file_ocr(file_path, filename)
        return _ocr_result_to_dataframe(result)
    except Exception as exc:
        logger.warning("Image OCR parse failed for %s: %s", filename, exc)
        return pd.DataFrame(
            [
                {
                    "raw_content": f"[Image stored for manual review — OCR unavailable: {filename}]",
                    "source_file": filename,
                }
            ]
        )


def load_file_as_dataframe(file_path: str, filename: str) -> Tuple[pd.DataFrame, str, str]:
    """
    Returns (dataframe, file_format, source_type).
    Applies universal header canonicalization.
    """
    fmt = detect_file_format(filename)
    if fmt == "csv":
        df = parse_csv(file_path)
    elif fmt == "xlsx":
        df = parse_xlsx(file_path)
    elif fmt == "json":
        df = parse_json(file_path)
    elif fmt == "xml":
        df = parse_xml(file_path)
    elif fmt == "pdf":
        df = parse_pdf(file_path, filename)
    elif fmt == "txt":
        df = parse_txt(file_path)
    elif fmt == "image":
        df = parse_image(file_path, filename)
    else:
        raise ValueError(f"Unsupported file format: {fmt}")

    if df is None or df.empty:
        return pd.DataFrame(), fmt, detect_source_type(filename, [])

    df, column_mapping = canonicalize_columns(df)
    source = detect_source_type(filename, list(df.columns))
    return df, fmt, source


def is_supported_upload(filename: str) -> bool:
    return Path(filename or "").suffix.lower() in SUPPORTED_EXTENSIONS
