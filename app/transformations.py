"""Data cleaning, KPI calculations, and executive classifications."""

from __future__ import annotations

import math
import re
from calendar import month_abbr
from typing import Any

import numpy as np
import pandas as pd

import config


EMPTY_TOKENS = {"", "na", "n/a", "none", "null", "-", "--"}
MIN_VALID_YEAR = 1900
MAX_VALID_YEAR = 2100


def _standardise_text(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()
    if text.lower() in EMPTY_TOKENS:
        return None

    words = []
    for word in text.split(" "):
        if word.isupper() and len(word) <= 3:
            words.append(word)
        elif word.isupper() or word.islower():
            words.append(word.capitalize())
        else:
            words.append(word)
    return " ".join(words)


def _parse_period_value(value: Any) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return _valid_business_period(value)

    text = str(value).strip()
    if text.lower() in EMPTY_TOKENS:
        return pd.NaT

    quarter_patterns = (
        r"^(?P<year>\d{4})\s*[- ]?\s*q(?P<quarter>[1-4])$",
        r"^q(?P<quarter>[1-4])\s*[- ]?\s*(?P<year>\d{4})$",
    )
    for pattern in quarter_patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            year = int(match.group("year"))
            quarter = int(match.group("quarter"))
            month = (quarter - 1) * 3 + 1
            return _valid_business_period(pd.Timestamp(year=year, month=month, day=1))

    numeric_text = re.sub(r"\.0$", "", text)
    digits_only = re.sub(r"\D", "", numeric_text)
    if digits_only:
        if len(digits_only) == 6:
            parsed = pd.to_datetime(digits_only, format="%Y%m", errors="coerce")
            return _valid_business_period(parsed)
        if len(digits_only) == 8:
            parsed = pd.to_datetime(digits_only, format="%Y%m%d", errors="coerce")
            return _valid_business_period(parsed)
        if len(digits_only) == 4:
            parsed = pd.to_datetime(f"{digits_only}0101", format="%Y%m%d", errors="coerce")
            return _valid_business_period(parsed)

    if isinstance(value, (int, float, np.number)) and 20_000 <= float(value) <= 60_000:
        parsed = pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
        return _valid_business_period(parsed)

    parsed = pd.to_datetime(text, errors="coerce")
    return _valid_business_period(parsed)


def _valid_business_period(value: Any) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    timestamp = pd.Timestamp(value).normalize()
    if MIN_VALID_YEAR <= timestamp.year <= MAX_VALID_YEAR:
        return timestamp
    return pd.NaT


def _parse_numeric_value(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.number)) and math.isfinite(float(value)):
        return float(value)

    text = str(value).strip().replace("\u00a0", " ")
    if text.lower() in EMPTY_TOKENS:
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[-1]) in {1, 2}:
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")

    try:
        number = float(text)
    except ValueError:
        return None
    return -number if is_negative else number


def prepare_revenue_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean and enrich source data for dashboard use."""
    df = raw.copy()
    initial_rows = len(df)

    missing_required_columns = [field for field in config.REQUIRED_FIELDS if field not in df.columns]
    if missing_required_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_required_columns)}")

    period_raw = df["period"].copy()
    revenue_raw = df["ext_invoice"].copy()

    df["period"] = df["period"].map(_parse_period_value)
    df["ext_invoice"] = df["ext_invoice"].map(_parse_numeric_value)
    df["industry"] = df["industry"].map(_standardise_text)
    df["country"] = df["country"].map(_standardise_text)

    invalid_period_count = int(period_raw.notna().sum() - df["period"].notna().sum())
    invalid_revenue_count = int(revenue_raw.notna().sum() - df["ext_invoice"].notna().sum())

    critical_missing_mask = (
        df["period"].isna()
        | df["industry"].isna()
        | df["country"].isna()
        | df["ext_invoice"].isna()
    )
    critical_missing_count = int(critical_missing_mask.sum())

    df = df.loc[~critical_missing_mask, list(config.REQUIRED_FIELDS)].copy()
    df["period"] = pd.to_datetime(df["period"]).dt.to_period("M").dt.to_timestamp()
    df["year"] = df["period"].dt.year.astype(int)
    df["quarter"] = df["period"].dt.quarter.astype(int)
    df["month"] = df["period"].dt.month.astype(int)
    df["year_quarter_start"] = df["period"].dt.to_period("Q").dt.start_time
    df["year_quarter"] = df.apply(lambda row: f"{int(row['year'])} Q{int(row['quarter'])}", axis=1)
    df["year_month"] = df["period"].dt.strftime("%Y-%m")

    df = df.sort_values(["period", "industry", "country"]).reset_index(drop=True)

    quality = {
        "initial_rows": int(initial_rows),
        "rows_after_cleaning": int(len(df)),
        "dropped_rows": int(initial_rows - len(df)),
        "invalid_period_count": invalid_period_count,
        "invalid_revenue_count": invalid_revenue_count,
        "critical_missing_count": critical_missing_count,
        "date_min": df["period"].min() if not df.empty else pd.NaT,
        "date_max": df["period"].max() if not df.empty else pd.NaT,
        "revenue_min": float(df["ext_invoice"].min()) if not df.empty else None,
        "revenue_max": float(df["ext_invoice"].max()) if not df.empty else None,
        "total_revenue": float(df["ext_invoice"].sum()) if not df.empty else 0.0,
    }
    return df, quality


def filter_revenue_data(
    df: pd.DataFrame,
    *,
    date_range: tuple[Any, Any] | None = None,
    years: list[int] | None = None,
    quarters: list[int] | None = None,
    industries: list[str] | None = None,
    countries: list[str] | None = None,
) -> pd.DataFrame:
    filtered = df.copy()

    if date_range and len(date_range) == 2:
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1]) + pd.offsets.MonthEnd(0)
        filtered = filtered[(filtered["period"] >= start) & (filtered["period"] <= end)]

    if years:
        filtered = filtered[filtered["year"].isin(years)]
    if quarters:
        filtered = filtered[filtered["quarter"].isin(quarters)]
    if industries:
        filtered = filtered[filtered["industry"].isin(industries)]
    if countries:
        filtered = filtered[filtered["country"].isin(countries)]

    return filtered.copy()


def _growth_pct(current: float | None, previous: float | None) -> float | None:
    if previous is None or previous == 0 or pd.isna(previous):
        return None
    if current is None or pd.isna(current):
        current = 0.0
    return ((float(current) - float(previous)) / abs(float(previous))) * 100


def calculate_kpis(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "total_revenue": 0.0,
            "country_count": 0,
            "industry_count": 0,
            "yoy_growth_pct": None,
            "qoq_growth_pct": None,
            "latest_year": None,
            "previous_year": None,
            "yoy_comparison": "Comparison unavailable",
            "latest_quarter": None,
            "previous_quarter": None,
        }

    latest_year = int(df["year"].max())
    previous_year = latest_year - 1
    latest_months = sorted(df.loc[df["year"] == latest_year, "month"].unique().tolist())
    latest_year_revenue = df.loc[
        (df["year"] == latest_year) & (df["month"].isin(latest_months)),
        "ext_invoice",
    ].sum()
    previous_comparable = df.loc[
        (df["year"] == previous_year) & (df["month"].isin(latest_months)),
        ["month", "ext_invoice"],
    ]
    has_comparable_previous = previous_comparable["month"].nunique() == len(latest_months)
    previous_year_revenue = previous_comparable["ext_invoice"].sum()
    yoy_growth = _growth_pct(
        latest_year_revenue,
        previous_year_revenue if has_comparable_previous and previous_year_revenue else None,
    )
    month_label = _month_window_label(latest_months)
    yoy_comparison = (
        f"{month_label} {previous_year} to {month_label} {latest_year}"
        if has_comparable_previous
        else "Comparison unavailable"
    )

    quarterly = (
        df.groupby(["year_quarter_start", "year_quarter"], as_index=False)["ext_invoice"]
        .sum()
        .sort_values("year_quarter_start")
    )
    latest_quarter_label = quarterly["year_quarter"].iloc[-1]
    previous_quarter_label = quarterly["year_quarter"].iloc[-2] if len(quarterly) > 1 else None
    qoq_growth = None
    if len(quarterly) > 1:
        qoq_growth = _growth_pct(
            quarterly["ext_invoice"].iloc[-1],
            quarterly["ext_invoice"].iloc[-2],
        )

    return {
        "total_revenue": float(df["ext_invoice"].sum()),
        "country_count": int(df["country"].nunique()),
        "industry_count": int(df["industry"].nunique()),
        "yoy_growth_pct": yoy_growth,
        "qoq_growth_pct": qoq_growth,
        "latest_year": latest_year,
        "previous_year": previous_year if previous_year_revenue else None,
        "yoy_comparison": yoy_comparison,
        "latest_quarter": latest_quarter_label,
        "previous_quarter": previous_quarter_label,
    }


def _month_window_label(months: list[int]) -> str:
    if not months:
        return "N/A"
    if len(months) == 1:
        return month_abbr[months[0]]
    return f"{month_abbr[months[0]]}-{month_abbr[months[-1]]}"


def top_contributors(df: pd.DataFrame, dimension: str, n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[dimension, "ext_invoice", "share_pct"])
    grouped = (
        df.groupby(dimension, as_index=False)["ext_invoice"]
        .sum()
        .sort_values("ext_invoice", ascending=False)
    )
    total = grouped["ext_invoice"].sum()
    grouped["share_pct"] = np.where(total != 0, grouped["ext_invoice"] / total * 100, np.nan)
    return grouped.head(n).reset_index(drop=True)


def build_traffic_light_table(
    df: pd.DataFrame,
    *,
    green_threshold: float = config.GREEN_THRESHOLD,
    red_threshold: float = config.RED_THRESHOLD,
) -> tuple[pd.DataFrame, str | None, str | None]:
    if df.empty:
        columns = [
            "Industry",
            "Country",
            "Current Revenue",
            "Previous Revenue",
            "Growth %",
            "Status",
            "Recommendation",
        ]
        return pd.DataFrame(columns=columns), None, None

    periods = (
        df[["year_quarter_start", "year_quarter"]]
        .drop_duplicates()
        .sort_values("year_quarter_start")
        .reset_index(drop=True)
    )
    current_start = periods["year_quarter_start"].iloc[-1]
    current_label = str(periods["year_quarter"].iloc[-1])
    previous_start = periods["year_quarter_start"].iloc[-2] if len(periods) > 1 else None
    previous_label = str(periods["year_quarter"].iloc[-2]) if len(periods) > 1 else None

    current = (
        df.loc[df["year_quarter_start"] == current_start]
        .groupby(["industry", "country"], as_index=False)["ext_invoice"]
        .sum()
        .rename(columns={"ext_invoice": "Current Revenue"})
    )
    if previous_start is not None:
        previous = (
            df.loc[df["year_quarter_start"] == previous_start]
            .groupby(["industry", "country"], as_index=False)["ext_invoice"]
            .sum()
            .rename(columns={"ext_invoice": "Previous Revenue"})
        )
    else:
        previous = pd.DataFrame(columns=["industry", "country", "Previous Revenue"])

    table = current.merge(previous, on=["industry", "country"], how="outer")
    table["Current Revenue"] = table["Current Revenue"].fillna(0.0)
    table["Previous Revenue"] = table["Previous Revenue"].fillna(0.0)
    table["Growth %"] = table.apply(
        lambda row: _growth_pct(row["Current Revenue"], row["Previous Revenue"]),
        axis=1,
    )

    def classify(growth: float | None) -> str:
        if growth is None or pd.isna(growth):
            return "N/A"
        if growth > green_threshold:
            return "Green"
        if growth < red_threshold:
            return "Red"
        return "Yellow"

    table["Status"] = table["Growth %"].map(classify)
    table["Recommendation"] = table["Status"].map(config.TRAFFIC_LIGHT_RECOMMENDATIONS)
    table = table.rename(columns={"industry": "Industry", "country": "Country"})
    table = table[
        [
            "Industry",
            "Country",
            "Current Revenue",
            "Previous Revenue",
            "Growth %",
            "Status",
            "Recommendation",
        ]
    ].sort_values(["Status", "Growth %", "Current Revenue"], ascending=[True, True, False])
    return table.reset_index(drop=True), current_label, previous_label
