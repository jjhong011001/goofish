"""Export item records to CSV or Excel."""

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

ALL_FIELDS = [
    "item_id", "title", "price", "condition",
    "seller_nick", "location", "category",
    "want_count", "created_time", "images",
]


def export(
    items: list[dict],
    keyword: str,
    fmt: Literal["csv", "excel"] = "csv",
    fields: Optional[list[str]] = None,
) -> Path:
    """Export items to CSV or Excel and return the output file path.

    Args:
        fields: List of field names to include. None means all fields.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(" ", "_").replace("/", "-")[:30]

    df = pd.DataFrame(items)
    if df.empty:
        raise ValueError("No items to export.")

    # Determine column order
    ordered = fields if fields else ALL_FIELDS
    cols = [c for c in ordered if c in df.columns]
    df = df[cols]

    if fmt == "excel":
        out_path = DATA_DIR / f"{safe_keyword}_{timestamp}.xlsx"
        df.to_excel(out_path, index=False, engine="openpyxl")
    else:
        out_path = DATA_DIR / f"{safe_keyword}_{timestamp}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")

    return out_path
