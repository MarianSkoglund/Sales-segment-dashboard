"""Plotly chart builders for the executive revenue dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import config


def _empty_figure(title: str, message: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": config.KNOWIT_COLORS["slate"], "size": 15},
    )
    fig.update_layout(
        title=title,
        height=360,
        template=config.PLOTLY_TEMPLATE,
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"l": 20, "r": 20, "t": 70, "b": 20},
    )
    return fig


def _apply_board_layout(fig: go.Figure, title: str, height: int = 390) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template=config.PLOTLY_TEMPLATE,
        height=height,
        colorway=config.CHART_COLOR_SEQUENCE,
        hoverlabel={"bgcolor": "white", "font_size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"l": 40, "r": 30, "t": 80, "b": 45},
        font={"family": "Inter, Segoe UI, Arial, sans-serif", "color": config.KNOWIT_COLORS["charcoal"]},
    )
    fig.update_xaxes(showgrid=False, linecolor=config.KNOWIT_COLORS["line"])
    fig.update_yaxes(gridcolor="#E8EEF3", zeroline=False)
    return fig


def revenue_donut(
    df: pd.DataFrame,
    dimension: str,
    title: str,
    max_slices: int = config.MAX_DONUT_SLICES,
) -> go.Figure:
    if df.empty:
        return _empty_figure(title)

    grouped = (
        df.groupby(dimension, as_index=False)["ext_invoice"]
        .sum()
        .sort_values("ext_invoice", ascending=False)
    )
    if len(grouped) > max_slices:
        top = grouped.head(max_slices - 1).copy()
        other_value = grouped.iloc[max_slices - 1 :]["ext_invoice"].sum()
        grouped = pd.concat(
            [
                top,
                pd.DataFrame([{dimension: "Other", "ext_invoice": other_value}]),
            ],
            ignore_index=True,
        )

    fig = px.pie(
        grouped,
        names=dimension,
        values="ext_invoice",
        hole=0.58,
        color_discrete_sequence=config.CHART_COLOR_SEQUENCE,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Revenue: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
        marker={"line": {"color": "white", "width": 2}},
    )
    fig.update_layout(showlegend=True)
    return _apply_board_layout(fig, title, height=410)


def revenue_trend_by_year(df: pd.DataFrame) -> go.Figure:
    title = "Revenue Trend by Year"
    if df.empty:
        return _empty_figure(title)

    trend = df.groupby("year", as_index=False)["ext_invoice"].sum().sort_values("year")
    fig = px.line(
        trend,
        x="year",
        y="ext_invoice",
        markers=True,
        color_discrete_sequence=[config.KNOWIT_COLORS["red"]],
    )
    fig.update_traces(
        line={"width": 3},
        marker={"size": 9},
        hovertemplate="<b>%{x}</b><br>Revenue: %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(title=config.REVENUE_LABEL, tickformat=",.0f")
    fig.update_xaxes(title="", dtick=1)
    return _apply_board_layout(fig, title)


def revenue_trend_by_quarter(df: pd.DataFrame) -> go.Figure:
    title = "Revenue Trend by Quarter"
    if df.empty:
        return _empty_figure(title)

    trend = (
        df.groupby(["year_quarter_start", "year_quarter"], as_index=False)["ext_invoice"]
        .sum()
        .sort_values("year_quarter_start")
    )
    fig = px.line(
        trend,
        x="year_quarter",
        y="ext_invoice",
        markers=True,
        color_discrete_sequence=[config.KNOWIT_COLORS["teal"]],
    )
    fig.update_traces(
        line={"width": 3},
        marker={"size": 8},
        hovertemplate="<b>%{x}</b><br>Revenue: %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(title=config.REVENUE_LABEL, tickformat=",.0f")
    fig.update_xaxes(title="", type="category")
    return _apply_board_layout(fig, title)


def multi_line_trend(
    df: pd.DataFrame,
    *,
    category_column: str,
    title: str,
    selected_categories: list[str] | None = None,
) -> go.Figure:
    if df.empty:
        return _empty_figure(title)

    chart_df = df.copy()
    if selected_categories:
        chart_df = chart_df[chart_df[category_column].isin(selected_categories)]
    if chart_df.empty:
        return _empty_figure(title, "No selected segment has data")

    trend = (
        chart_df.groupby(["year_quarter_start", "year_quarter", category_column], as_index=False)["ext_invoice"]
        .sum()
        .sort_values("year_quarter_start")
    )
    fig = px.line(
        trend,
        x="year_quarter",
        y="ext_invoice",
        color=category_column,
        markers=True,
        color_discrete_sequence=config.CHART_COLOR_SEQUENCE,
    )
    fig.update_traces(
        line={"width": 2.5},
        marker={"size": 7},
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Revenue: %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(title=config.REVENUE_LABEL, tickformat=",.0f")
    fig.update_xaxes(title="", type="category")
    return _apply_board_layout(fig, title, height=450)


def industry_country_trend(
    df: pd.DataFrame,
    *,
    industries: list[str] | None = None,
    countries: list[str] | None = None,
) -> go.Figure:
    title = "Industry-Country Trend Analysis"
    if df.empty:
        return _empty_figure(title)

    chart_df = df.copy()
    if industries:
        chart_df = chart_df[chart_df["industry"].isin(industries)]
    if countries:
        chart_df = chart_df[chart_df["country"].isin(countries)]
    if chart_df.empty:
        return _empty_figure(title, "No selected combination has data")

    chart_df = chart_df.assign(segment=chart_df["industry"] + " | " + chart_df["country"])
    trend = (
        chart_df.groupby(["year_quarter_start", "year_quarter", "segment"], as_index=False)["ext_invoice"]
        .sum()
        .sort_values("year_quarter_start")
    )
    fig = px.line(
        trend,
        x="year_quarter",
        y="ext_invoice",
        color="segment",
        markers=True,
        color_discrete_sequence=config.CHART_COLOR_SEQUENCE,
    )
    fig.update_traces(
        line={"width": 2.3},
        marker={"size": 6},
        hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>Revenue: %{y:,.0f}<extra></extra>",
    )
    fig.update_yaxes(title=config.REVENUE_LABEL, tickformat=",.0f")
    fig.update_xaxes(title="", type="category")
    return _apply_board_layout(fig, title, height=500)


def industry_country_heatmap(df: pd.DataFrame) -> go.Figure:
    title = "Industry vs Country Revenue Matrix"
    if df.empty:
        return _empty_figure(title)

    top_industries = (
        df.groupby("industry")["ext_invoice"]
        .sum()
        .sort_values(ascending=False)
        .head(config.MAX_HEATMAP_CATEGORIES)
        .index
    )
    top_countries = (
        df.groupby("country")["ext_invoice"]
        .sum()
        .sort_values(ascending=False)
        .head(config.MAX_HEATMAP_CATEGORIES)
        .index
    )
    chart_df = df[df["industry"].isin(top_industries) & df["country"].isin(top_countries)]
    matrix = chart_df.pivot_table(
        index="industry",
        columns="country",
        values="ext_invoice",
        aggfunc="sum",
        fill_value=0.0,
    )
    if matrix.empty:
        return _empty_figure(title)

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            colorscale=[
                [0, "#F4F7F9"],
                [0.25, "#C9E9EA"],
                [0.6, "#36A8AF"],
                [1, "#1F2933"],
            ],
            colorbar={"title": config.REVENUE_LABEL, "tickformat": ",.0f"},
            hovertemplate=(
                "<b>%{y}</b><br>"
                + config.COUNTRY_LABEL
                + ": %{x}<br>Revenue: %{z:,.0f}<extra></extra>"
            ),
        )
    )
    fig.update_xaxes(title="", tickangle=-35)
    fig.update_yaxes(title="", autorange="reversed")
    return _apply_board_layout(fig, title, height=max(460, 24 * len(matrix.index) + 180))
