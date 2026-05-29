"""Configuration for the executive revenue analytics dashboard."""

from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DEFAULT_EXCEL_FILENAME = "Adjusted gross sales combined 2024-2026Q1.xlsx"
DEFAULT_EXCEL_PATH = APP_DIR / DEFAULT_EXCEL_FILENAME

PAGE_TITLE = "Executive Revenue Analytics"
PAGE_ICON = "bar_chart"

REQUIRED_FIELDS = ("period", "industry", "country", "ext_invoice")

# Zero-based column positions detected from the source workbook.
SOURCE_COLUMN_MAPPING = {
    "ext_invoice": {
        "excel_column": "D",
        "position": 3,
        "detected_name": "Ext. invoice",
        "business_meaning": "Ext. Invoice",
    },
    "industry": {
        "excel_column": "H",
        "position": 7,
        "detected_name": "Industry",
        "business_meaning": "Industry",
    },
    "country": {
        "excel_column": "M",
        "position": 12,
        "detected_name": "BA Region (T)",
        "business_meaning": "Country / Region",
    },
    "period": {
        "excel_column": "T",
        "position": 19,
        "detected_name": "Period",
        "business_meaning": "Date / Period",
    },
}

HEADER_SCAN_ROWS = 30

GREEN_THRESHOLD = 10.0
RED_THRESHOLD = -10.0

REVENUE_LABEL = "Ext. Invoice"
COUNTRY_LABEL = "Country / Region"

MAX_DONUT_SLICES = 10
MAX_HEATMAP_CATEGORIES = 30
DEFAULT_TREND_SELECTION_SIZE = 6

KNOWIT_COLORS = {
    "charcoal": "#1F2933",
    "slate": "#52616B",
    "mist": "#F4F7F9",
    "line": "#D7DEE4",
    "red": "#E23D3D",
    "coral": "#FF6B5F",
    "teal": "#008C95",
    "blue": "#2563EB",
    "yellow": "#F3B61F",
    "green": "#1E9E5A",
}

CHART_COLOR_SEQUENCE = [
    KNOWIT_COLORS["red"],
    KNOWIT_COLORS["teal"],
    KNOWIT_COLORS["blue"],
    KNOWIT_COLORS["yellow"],
    KNOWIT_COLORS["coral"],
    KNOWIT_COLORS["green"],
    "#7C3AED",
    "#0F766E",
    "#EA580C",
    "#475569",
]

PLOTLY_TEMPLATE = "plotly_white"

TRAFFIC_LIGHT_RECOMMENDATIONS = {
    "Green": "Strong growth - consider increased focus.",
    "Yellow": "Stable performance - monitor closely.",
    "Red": "Declining performance - investigate drivers.",
    "N/A": "Insufficient prior-period data.",
}
