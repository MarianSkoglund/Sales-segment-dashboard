"""Streamlit executive revenue analytics dashboard."""

from __future__ import annotations

import logging
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

import charts
import config
from data_loader import DataValidationError, create_mock_revenue_data, load_revenue_source
from transformations import (
    build_traffic_light_table,
    calculate_kpis,
    filter_revenue_data,
    prepare_revenue_data,
    top_contributors,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


st.set_page_config(
    page_title=config.PAGE_TITLE,
    page_icon=config.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --knowit-charcoal: #1F2933;
            --knowit-slate: #52616B;
            --knowit-mist: #F4F7F9;
            --knowit-line: #D7DEE4;
            --knowit-red: #E23D3D;
            --knowit-teal: #008C95;
        }
        .block-container {
            padding-top: 1.7rem;
            padding-bottom: 3rem;
            max-width: 1480px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
            color: var(--knowit-charcoal);
        }
        .app-subtitle {
            color: var(--knowit-slate);
            font-size: 1rem;
            margin-top: -0.55rem;
            margin-bottom: 1.25rem;
        }
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid var(--knowit-line);
            border-top: 4px solid var(--accent-color);
            border-radius: 8px;
            padding: 1rem 1.05rem;
            min-height: 122px;
            box-shadow: 0 8px 24px rgba(31, 41, 51, 0.06);
        }
        .kpi-label {
            color: var(--knowit-slate);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }
        .kpi-value {
            color: var(--knowit-charcoal);
            font-size: 1.55rem;
            line-height: 1.2;
            font-weight: 760;
            overflow-wrap: anywhere;
        }
        .kpi-helper {
            color: var(--knowit-slate);
            font-size: 0.82rem;
            margin-top: 0.45rem;
        }
        .insight-panel {
            background: #FFFFFF;
            border: 1px solid var(--knowit-line);
            border-radius: 8px;
            padding: 1rem 1.15rem;
            margin: 0.35rem 0 1rem 0;
        }
        .insight-panel strong {
            color: var(--knowit-charcoal);
        }
        .section-note {
            color: var(--knowit-slate);
            font-size: 0.92rem;
            margin-top: -0.35rem;
            margin-bottom: 0.9rem;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid var(--knowit-line);
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--knowit-line);
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_revenue(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.0f}"


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):+.1f}%"


def kpi_card(label: str, value: str, helper: str, accent: str) -> str:
    return f"""
    <div class="kpi-card" style="--accent-color: {accent};">
        <div class="kpi-label">{escape(label)}</div>
        <div class="kpi-value">{escape(value)}</div>
        <div class="kpi-helper">{escape(helper)}</div>
    </div>
    """


@st.cache_data(show_spinner=False)
def load_and_prepare_source(source_kind: str, source_payload: str | bytes) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    source: str | bytes = source_payload
    raw, diagnostics = load_revenue_source(source)
    prepared, quality = prepare_revenue_data(raw)
    return prepared, diagnostics, quality


def load_default_or_mock() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    if config.DEFAULT_EXCEL_PATH.exists():
        return load_and_prepare_source("path", str(config.DEFAULT_EXCEL_PATH))

    raw, diagnostics = create_mock_revenue_data()
    prepared, quality = prepare_revenue_data(raw)
    diagnostics["is_mock"] = True
    return prepared, diagnostics, quality


def render_kpis(df: pd.DataFrame) -> None:
    kpis = calculate_kpis(df)
    cards = [
        (
            "Total Ext. Invoice",
            format_revenue(kpis["total_revenue"]),
            "Filtered revenue",
            config.KNOWIT_COLORS["red"],
        ),
        (
            "Market Coverage",
            f"{kpis['country_count']:,}",
            config.COUNTRY_LABEL,
            config.KNOWIT_COLORS["teal"],
        ),
        (
            "Industry Coverage",
            f"{kpis['industry_count']:,}",
            "Distinct industries",
            config.KNOWIT_COLORS["blue"],
        ),
        (
            "YoY Growth",
            format_pct(kpis["yoy_growth_pct"]),
            kpis["yoy_comparison"],
            config.KNOWIT_COLORS["green"],
        ),
        (
            "QoQ Growth",
            format_pct(kpis["qoq_growth_pct"]),
            _comparison_helper(kpis["latest_quarter"], kpis["previous_quarter"]),
            config.KNOWIT_COLORS["yellow"],
        ),
    ]

    cols = st.columns(5)
    for column, card in zip(cols, cards, strict=True):
        with column:
            st.markdown(kpi_card(*card), unsafe_allow_html=True)


def _comparison_helper(current: Any, previous: Any) -> str:
    if current is None or previous is None:
        return "Comparison unavailable"
    return f"{previous} to {current}"


def default_dimension_selection(df: pd.DataFrame, dimension: str) -> list[str]:
    return (
        df.groupby(dimension)["ext_invoice"]
        .sum()
        .sort_values(ascending=False)
        .head(config.DEFAULT_TREND_SELECTION_SIZE)
        .index
        .tolist()
    )


def render_top_table(df: pd.DataFrame, dimension: str, label: str) -> None:
    table = top_contributors(df, dimension, n=12).rename(
        columns={dimension: label, "ext_invoice": "Revenue", "share_pct": "Share %"}
    )
    st.dataframe(
        table.style.format({"Revenue": "{:,.0f}", "Share %": "{:.1f}%"}),
        use_container_width=True,
        hide_index=True,
    )


def render_strategic_summary(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No data is available for the selected filters.")
        return

    top_industry = top_contributors(df, "industry", n=1)
    top_country = top_contributors(df, "country", n=1)
    kpis = calculate_kpis(df)
    industry_text = (
        f"<strong>{escape(str(top_industry.iloc[0]['industry']))}</strong> contributes "
        f"{top_industry.iloc[0]['share_pct']:.1f}% of filtered revenue."
    )
    country_text = (
        f"<strong>{escape(str(top_country.iloc[0]['country']))}</strong> contributes "
        f"{top_country.iloc[0]['share_pct']:.1f}% of filtered revenue."
    )
    growth_text = (
        f"Latest QoQ growth is <strong>{format_pct(kpis['qoq_growth_pct'])}</strong> "
        f"and YoY growth is <strong>{format_pct(kpis['yoy_growth_pct'])}</strong>."
    )
    st.markdown(
        f"""
        <div class="insight-panel">
            {industry_text}<br>
            {country_text}<br>
            {growth_text}
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_traffic_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def status_style(value: str) -> str:
        styles = {
            "Green": "background-color: #E5F6EE; color: #0B6B3A; font-weight: 700;",
            "Yellow": "background-color: #FFF6D8; color: #8A5A00; font-weight: 700;",
            "Red": "background-color: #FDE9E9; color: #A01818; font-weight: 700;",
            "N/A": "background-color: #F1F5F9; color: #52616B; font-weight: 700;",
        }
        return styles.get(value, "")

    styler = df.style.format(
        {
            "Current Revenue": "{:,.0f}",
            "Previous Revenue": "{:,.0f}",
            "Growth %": lambda value: "N/A" if pd.isna(value) else f"{value:+.1f}%",
        }
    )
    if hasattr(styler, "map"):
        return styler.map(status_style, subset=["Status"])
    return styler.applymap(status_style, subset=["Status"])


def mapping_dataframe(diagnostics: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for semantic_name, details in diagnostics["detected_mapping"].items():
        rows.append(
            {
                "Excel Column": details["excel_column"],
                "Detected Header": details["actual_name"],
                "Dashboard Field": semantic_name,
                "Business Meaning": details["business_meaning"],
            }
        )
    return pd.DataFrame(rows)


def quality_dataframe(quality: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("Rows loaded", quality["initial_rows"]),
        ("Rows retained after cleaning", quality["rows_after_cleaning"]),
        ("Rows removed", quality["dropped_rows"]),
        ("Invalid period values", quality["invalid_period_count"]),
        ("Invalid revenue values", quality["invalid_revenue_count"]),
        ("Rows missing critical fields", quality["critical_missing_count"]),
        ("Earliest period", quality["date_min"].strftime("%Y-%m") if pd.notna(quality["date_min"]) else "N/A"),
        ("Latest period", quality["date_max"].strftime("%Y-%m") if pd.notna(quality["date_max"]) else "N/A"),
        ("Total revenue", format_revenue(quality["total_revenue"])),
    ]
    return pd.DataFrame(rows, columns=["Check", "Value"])


def main() -> None:
    apply_custom_css()

    st.title(config.PAGE_TITLE)
    st.markdown(
        '<div class="app-subtitle">Board-ready revenue performance by industry, country/region, and time period.</div>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Data Source")
        uploaded_file = st.file_uploader(
            "Replace source workbook",
            type=["xlsx", "xlsm"],
            help="The workbook must contain the required fields in columns D, H, M, and T.",
        )

    try:
        if uploaded_file is not None:
            prepared_df, diagnostics, quality = load_and_prepare_source("upload", uploaded_file.getvalue())
            source_name = uploaded_file.name
        else:
            prepared_df, diagnostics, quality = load_default_or_mock()
            source_name = (
                config.DEFAULT_EXCEL_PATH.name
                if config.DEFAULT_EXCEL_PATH.exists()
                else "Mock fallback data"
            )
    except FileNotFoundError:
        st.error(
            "The default workbook was not found. Place the Excel file in the app folder or upload a workbook in the sidebar."
        )
        st.stop()
    except DataValidationError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # pragma: no cover - UI level safety net
        logger.exception("Unexpected dashboard loading failure")
        st.error("The workbook could not be loaded. Please confirm the file is a valid Excel workbook.")
        st.caption(str(exc))
        st.stop()

    if prepared_df.empty:
        st.error("No valid records remain after cleaning. Check the Data Quality tab for diagnostics.")
        st.stop()

    with st.sidebar:
        st.caption(f"Source: {source_name}")
        if diagnostics.get("is_mock"):
            st.warning("Default workbook unavailable. Showing mock fallback data.")

        st.header("Global Filters")
        min_date = prepared_df["period"].min().date()
        max_date = prepared_df["period"].max().date()
        selected_date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if not isinstance(selected_date_range, tuple) or len(selected_date_range) != 2:
            selected_date_range = (min_date, max_date)

        year_options = sorted(prepared_df["year"].unique().tolist())
        quarter_options = sorted(prepared_df["quarter"].unique().tolist())
        industry_options = sorted(prepared_df["industry"].dropna().unique().tolist())
        country_options = sorted(prepared_df["country"].dropna().unique().tolist())

        selected_years = st.multiselect("Year", year_options, default=year_options)
        selected_quarters = st.multiselect(
            "Quarter",
            quarter_options,
            default=quarter_options,
            format_func=lambda quarter: f"Q{quarter}",
        )
        selected_industries = st.multiselect("Industry", industry_options, default=industry_options)
        selected_countries = st.multiselect(config.COUNTRY_LABEL, country_options, default=country_options)

    filtered_df = filter_revenue_data(
        prepared_df,
        date_range=selected_date_range,
        years=selected_years,
        quarters=selected_quarters,
        industries=selected_industries,
        countries=selected_countries,
    )

    render_kpis(filtered_df)

    tabs = st.tabs(
        [
            "Executive Overview",
            "Industry Analysis",
            "Country Analysis",
            "Industry-Country Analysis",
            "Traffic Light Analysis",
            "Data Quality",
        ]
    )

    with tabs[0]:
        st.subheader("Executive Overview")
        render_strategic_summary(filtered_df)
        left, right = st.columns(2)
        with left:
            st.plotly_chart(charts.revenue_donut(filtered_df, "industry", "Revenue by Industry"), use_container_width=True)
        with right:
            st.plotly_chart(charts.revenue_donut(filtered_df, "country", f"Revenue by {config.COUNTRY_LABEL}"), use_container_width=True)

        trend_left, trend_right = st.columns(2)
        with trend_left:
            st.plotly_chart(charts.revenue_trend_by_year(filtered_df), use_container_width=True)
        with trend_right:
            st.plotly_chart(charts.revenue_trend_by_quarter(filtered_df), use_container_width=True)

    with tabs[1]:
        st.subheader("Industry Analysis")
        st.markdown('<div class="section-note">Compare industry scale and development over time.</div>', unsafe_allow_html=True)
        default_industries = default_dimension_selection(filtered_df, "industry")
        industry_selection = st.multiselect(
            "Industries to compare",
            sorted(filtered_df["industry"].unique().tolist()),
            default=default_industries,
            key="industry_trend_selection",
        )
        st.plotly_chart(
            charts.multi_line_trend(
                filtered_df,
                category_column="industry",
                title="Industry Trend Analysis",
                selected_categories=industry_selection,
            ),
            use_container_width=True,
        )
        render_top_table(filtered_df, "industry", "Industry")

    with tabs[2]:
        st.subheader("Country Analysis")
        st.markdown('<div class="section-note">Review country or region concentration and growth patterns.</div>', unsafe_allow_html=True)
        default_countries = default_dimension_selection(filtered_df, "country")
        country_selection = st.multiselect(
            f"{config.COUNTRY_LABEL}s to compare",
            sorted(filtered_df["country"].unique().tolist()),
            default=default_countries,
            key="country_trend_selection",
        )
        st.plotly_chart(
            charts.multi_line_trend(
                filtered_df,
                category_column="country",
                title=f"{config.COUNTRY_LABEL} Trend Analysis",
                selected_categories=country_selection,
            ),
            use_container_width=True,
        )
        render_top_table(filtered_df, "country", config.COUNTRY_LABEL)

    with tabs[3]:
        st.subheader("Industry-Country Analysis")
        st.markdown('<div class="section-note">Identify the strongest cross-sectional revenue combinations.</div>', unsafe_allow_html=True)
        combo_left, combo_right = st.columns(2)
        with combo_left:
            selected_combo_industries = st.multiselect(
                "Industry selection",
                sorted(filtered_df["industry"].unique().tolist()),
                default=default_dimension_selection(filtered_df, "industry")[:3],
                key="combo_industries",
            )
        with combo_right:
            selected_combo_countries = st.multiselect(
                f"{config.COUNTRY_LABEL} selection",
                sorted(filtered_df["country"].unique().tolist()),
                default=default_dimension_selection(filtered_df, "country")[:3],
                key="combo_countries",
            )
        st.plotly_chart(
            charts.industry_country_trend(
                filtered_df,
                industries=selected_combo_industries,
                countries=selected_combo_countries,
            ),
            use_container_width=True,
        )
        st.plotly_chart(charts.industry_country_heatmap(filtered_df), use_container_width=True)

    with tabs[4]:
        st.subheader("Traffic Light Analysis")
        traffic_table, current_period, previous_period = build_traffic_light_table(filtered_df)
        if current_period and previous_period:
            st.caption(f"Current period: {current_period}. Previous period: {previous_period}.")
        elif current_period:
            st.caption(f"Current period: {current_period}. No previous period is available for comparison.")

        status_counts = traffic_table["Status"].value_counts().reindex(["Green", "Yellow", "Red", "N/A"]).fillna(0).astype(int)
        count_cols = st.columns(4)
        for column, status in zip(count_cols, ["Green", "Yellow", "Red", "N/A"], strict=True):
            with column:
                st.metric(status, f"{status_counts[status]:,}")

        st.dataframe(style_traffic_table(traffic_table), use_container_width=True, hide_index=True)
        st.download_button(
            "Download traffic-light table",
            data=traffic_table.to_csv(index=False).encode("utf-8"),
            file_name="traffic_light_analysis.csv",
            mime="text/csv",
        )

    with tabs[5]:
        st.subheader("Data Quality")
        source_cols = st.columns(3)
        with source_cols[0]:
            st.metric("Worksheet", diagnostics["selected_sheet"])
        with source_cols[1]:
            st.metric("Header Row", diagnostics["header_row_number"])
        with source_cols[2]:
            st.metric("Rows Loaded", f"{diagnostics.get('raw_rows_loaded', 0):,}")

        st.markdown("#### Detected Source Mapping")
        st.dataframe(mapping_dataframe(diagnostics), use_container_width=True, hide_index=True)

        st.markdown("#### Validation Summary")
        st.dataframe(quality_dataframe(quality), use_container_width=True, hide_index=True)

        st.markdown("#### Cleaned Data Preview")
        preview = filtered_df[
            [
                "period",
                "year",
                "quarter",
                "year_quarter",
                "industry",
                "country",
                "ext_invoice",
            ]
        ].head(200)
        st.dataframe(
            preview.style.format({"period": lambda value: value.strftime("%Y-%m"), "ext_invoice": "{:,.2f}"}),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
