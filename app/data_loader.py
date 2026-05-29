"""Excel ingestion and validation for the revenue analytics dashboard."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import config


logger = logging.getLogger(__name__)


class DataValidationError(ValueError):
    """Raised when the workbook cannot be mapped to the required schema."""


ExcelSource = str | Path | bytes | bytearray | io.BytesIO


def _coerce_excel_source(source: ExcelSource) -> str | Path | io.BytesIO:
    if isinstance(source, (bytes, bytearray)):
        return io.BytesIO(source)
    if isinstance(source, io.BytesIO):
        source.seek(0)
        return source
    return source


def _assert_file_exists(source: ExcelSource) -> None:
    if isinstance(source, (str, Path)) and not Path(source).exists():
        raise FileNotFoundError(f"Workbook not found: {source}")


def _normalise_header(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).strip().lower().split())


def _is_numeric_like(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, (int, float, np.number)):
        return True
    text = str(value).strip().replace(",", ".")
    try:
        float(text)
        return True
    except ValueError:
        return False


def _known_header_tokens() -> set[str]:
    configured = {
        details["detected_name"]
        for details in config.SOURCE_COLUMN_MAPPING.values()
    }
    expected = {
        "Date",
        "Period",
        "Industry",
        "Country",
        "Ext. invoice",
        "Ext Invoice",
        "BA Region (T)",
    }
    return {_normalise_header(value) for value in configured | expected}


def get_workbook_sheets(source: ExcelSource) -> list[str]:
    """Return visible sheet names from an Excel workbook."""
    _assert_file_exists(source)
    try:
        excel_file = pd.ExcelFile(_coerce_excel_source(source), engine="openpyxl")
    except Exception as exc:  # pragma: no cover - message depends on engine internals
        logger.exception("Unable to open workbook")
        raise DataValidationError("The selected file is not a readable Excel workbook.") from exc
    return list(excel_file.sheet_names)


def _read_header_preview(source: ExcelSource, sheet_name: str | int) -> pd.DataFrame:
    try:
        return pd.read_excel(
            _coerce_excel_source(source),
            sheet_name=sheet_name,
            header=None,
            nrows=config.HEADER_SCAN_ROWS,
            dtype=object,
            engine="openpyxl",
        )
    except Exception as exc:  # pragma: no cover - message depends on engine internals
        logger.exception("Unable to read workbook preview")
        raise DataValidationError("The workbook could not be inspected.") from exc


def _find_header_row(preview: pd.DataFrame) -> int:
    required_positions = [
        details["position"] for details in config.SOURCE_COLUMN_MAPPING.values()
    ]
    max_position = max(required_positions)
    if preview.shape[1] <= max_position:
        raise DataValidationError(
            "The workbook must contain at least 20 columns so that D, H, M, and T can be read."
        )

    known_headers = _known_header_tokens()
    best_row: int | None = None
    best_score = -1

    for row_index, row in preview.iterrows():
        values = [row.iloc[position] for position in required_positions]
        if any(pd.isna(value) or str(value).strip() == "" for value in values):
            continue

        score = 0
        for value in values:
            normalised = _normalise_header(value)
            if normalised in known_headers:
                score += 4
            if not _is_numeric_like(value):
                score += 1

        if score > best_score:
            best_row = int(row_index)
            best_score = score

    if best_row is None or best_score < 4:
        raise DataValidationError(
            "Could not identify a header row with usable values in columns D, H, M, and T."
        )
    return best_row


def inspect_workbook(source: ExcelSource) -> dict[str, Any]:
    """Inspect workbook structure and return the D/H/M/T field mapping."""
    _assert_file_exists(source)
    sheets = get_workbook_sheets(source)
    if not sheets:
        raise DataValidationError("The workbook does not contain any worksheets.")

    selected_sheet = sheets[0]
    preview = _read_header_preview(source, selected_sheet)
    header_row_index = _find_header_row(preview)
    header_row = preview.iloc[header_row_index]

    detected_mapping = {}
    for semantic_name, details in config.SOURCE_COLUMN_MAPPING.items():
        detected_mapping[semantic_name] = {
            **details,
            "actual_name": header_row.iloc[details["position"]],
        }

    return {
        "sheet_names": sheets,
        "selected_sheet": selected_sheet,
        "header_row_index": header_row_index,
        "header_row_number": header_row_index + 1,
        "detected_mapping": detected_mapping,
    }


def load_revenue_source(source: ExcelSource) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load only the detected D/H/M/T columns and rename them semantically."""
    diagnostics = inspect_workbook(source)
    fields_by_position = sorted(
        config.SOURCE_COLUMN_MAPPING,
        key=lambda field: config.SOURCE_COLUMN_MAPPING[field]["position"],
    )
    positions = [
        config.SOURCE_COLUMN_MAPPING[field]["position"]
        for field in fields_by_position
    ]

    try:
        raw = pd.read_excel(
            _coerce_excel_source(source),
            sheet_name=diagnostics["selected_sheet"],
            header=diagnostics["header_row_index"],
            usecols=positions,
            dtype=object,
            engine="openpyxl",
        )
    except Exception as exc:  # pragma: no cover - message depends on engine internals
        logger.exception("Unable to load selected workbook columns")
        raise DataValidationError("The required columns could not be loaded from the workbook.") from exc

    if raw.empty:
        raise DataValidationError("The workbook does not contain any data rows.")

    raw = raw.dropna(how="all")
    raw = raw.iloc[:, : len(fields_by_position)].copy()
    raw.columns = fields_by_position
    raw = raw.loc[:, list(config.REQUIRED_FIELDS)]

    diagnostics["raw_rows_loaded"] = int(len(raw))
    diagnostics["raw_columns_loaded"] = list(config.REQUIRED_FIELDS)
    return raw, diagnostics


def create_mock_revenue_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Create deterministic fallback data only when no workbook is available."""
    rng = np.random.default_rng(42)
    periods = pd.period_range("2024-01", "2026-03", freq="M")
    industries = ["Public Sector", "Media", "Finance", "Retail", "Energy", "Technology"]
    countries = ["Sweden", "Norway", "Denmark", "Finland", "Germany"]

    rows: list[dict[str, Any]] = []
    for period in periods:
        for industry in industries:
            for country in countries:
                base = rng.uniform(80, 420)
                seasonal = 1 + (period.quarter - 2) * 0.04
                trend = 1 + (period.year - 2024) * rng.uniform(-0.02, 0.09)
                rows.append(
                    {
                        "period": int(period.strftime("%Y%m")),
                        "industry": industry,
                        "country": country,
                        "ext_invoice": round(base * seasonal * trend, 2),
                    }
                )

    diagnostics = {
        "sheet_names": ["Mock fallback"],
        "selected_sheet": "Mock fallback",
        "header_row_number": 1,
        "detected_mapping": {
            field: {
                **details,
                "actual_name": details["detected_name"],
            }
            for field, details in config.SOURCE_COLUMN_MAPPING.items()
        },
        "raw_rows_loaded": len(rows),
        "raw_columns_loaded": list(config.REQUIRED_FIELDS),
        "is_mock": True,
    }
    return pd.DataFrame(rows, columns=config.REQUIRED_FIELDS), diagnostics
