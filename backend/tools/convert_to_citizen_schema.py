import argparse
import re
from pathlib import Path

import pandas as pd
from typing import Dict, List, Set

REQUIRED_COLUMNS = ["full_name", "mobile", "district", "village", "dob"]


def normalize_column_name(name: object) -> str:
    s = "" if name is None else str(name)
    s = s.strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


COLUMN_ALIASES = {
    "full_name": {
        "full_name",
        "fullname",
        "full name",
        "name",
        "customer_name",
        "customername",
        "subscriber_name",
        "subscribername",
        "beneficiary_name",
        "citizen_name",
    },
    "mobile": {
        "mobile",
        "mobile_no",
        "mobile_number",
        "phone",
        "phone_no",
        "phone_number",
        "msisdn",
        "contact",
        "contact_no",
        "contact_number",
    },
    "district": {"district", "dist", "district_name", "city", "city_name"},
    "village": {"village", "village_name", "locality", "area", "town", "mandal"},
    "dob": {"dob", "date_of_birth", "birth_date", "birthdate"},
}


def build_mapping(columns: List[str]) -> Dict[str, str]:
    """
    Returns {original_column_name: canonical_required_name}.
    If multiple columns match the same required name, the first one wins.
    """
    normalized_to_original: Dict[str, str] = {}
    for c in columns:
        n = normalize_column_name(c)
        if n and n not in normalized_to_original:
            normalized_to_original[n] = c

    mapping: Dict[str, str] = {}
    used_originals: Set[str] = set()

    for required in REQUIRED_COLUMNS:
        aliases = COLUMN_ALIASES.get(required, {required})
        for a in aliases:
            n = normalize_column_name(a)
            orig = normalized_to_original.get(n)
            if orig and orig not in used_originals:
                mapping[orig] = required
                used_originals.add(orig)
                break
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert any CSV into the citizen upload schema (full_name,mobile,district,village,dob)."
    )
    parser.add_argument("input", help="Input CSV path")
    parser.add_argument(
        "-o",
        "--output",
        help="Output CSV path (default: <input>_citizen.csv)",
        default=None,
    )
    parser.add_argument(
        "--encoding",
        help="CSV encoding (default: utf-8). Use 'latin1' if you get decode errors.",
        default="utf-8",
    )
    args = parser.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    out_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else in_path.with_name(f"{in_path.stem}_citizen.csv")
    )

    df = pd.read_csv(in_path, encoding=args.encoding)
    if df.empty:
        raise SystemExit("Input CSV has no rows.")

    mapping = build_mapping([str(c) for c in df.columns])
    if mapping:
        df = df.rename(columns=mapping)

    # Ensure required columns exist
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Output with required columns first, then everything else
    ordered = REQUIRED_COLUMNS + [c for c in df.columns if c not in REQUIRED_COLUMNS]
    df = df[ordered]

    df.to_csv(out_path, index=False, encoding="utf-8")

    found = [c for c in mapping.values()]
    missing = [c for c in REQUIRED_COLUMNS if c not in found]
    print("Saved:", out_path)
    print("Mapped columns:")
    for src, dst in mapping.items():
        print(f"  {src} -> {dst}")
    if missing:
        print("Created missing required columns as blank:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

