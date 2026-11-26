"""Reusable presentation helpers."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st


def show_chart(fig, key: str) -> None:
    config = {"displayModeBar": False}
    try:
        st.plotly_chart(fig, width="stretch", config=config, key=key)
    except TypeError:  # older Streamlit
        st.plotly_chart(fig, use_container_width=True, config=config, key=key)


def show_table(data, key: str | None = None, **kwargs) -> None:
    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    try:
        st.dataframe(df, hide_index=True, width="stretch", key=key, **kwargs)
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True, **kwargs)


def hero(title: str, subtitle: str, badges: list[str]) -> None:
    chips = "".join(f'<span class="badge">{escape(b)}</span>' for b in badges)
    st.markdown(f'<div class="hero"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p>'
                f'<div class="badges">{chips}</div></div>', unsafe_allow_html=True)


def kpi_grid(items: list[tuple[str, str, str]]) -> None:
    cells = "".join(f'<div class="kpi"><div class="label">{escape(label)}</div><div class="value">{escape(v)}</div>'
                    f'<div class="sub">{escape(s)}</div></div>' for label, v, s in items)
    st.markdown(f'<div class="kpis">{cells}</div>', unsafe_allow_html=True)


def insight_card(item: dict) -> None:
    action = f'<div class="action">→ {escape(item["action"])}</div>' if item.get("action") else ""
    st.markdown(f'<div class="insight {item["severity"]}"><div class="top"><span class="title">{escape(item["title"])}</span>'
                f'<span class="area">{escape(item["area"])}</span></div><div class="detail">{escape(item["detail"])}</div>'
                f'{action}</div>', unsafe_allow_html=True)


def sparkline_svg(values: list[float], color: str = "#6366F1") -> str:
    """Tiny inline-SVG area sparkline for KPI cards (no JS, no extra requests)."""
    if len(values) < 2:
        return ""
    w, h, pad = 200, 34, 3
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    pts = [(pad + i * (w - 2 * pad) / (len(values) - 1), h - pad - (v - lo) / span * (h - 2 * pad))
           for i, v in enumerate(values)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{pts[0][0]:.1f},{h} {line} {pts[-1][0]:.1f},{h}"
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none"><polygon points="{area}" fill="{color}" fill-opacity=".16"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round"/><circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{color}"/></svg>')


def pbi_cards(cards: list[dict]) -> None:
    """Power BI-style KPI cards: value, delta vs prior month and a sparkline."""
    html = []
    for c in cards:
        delta = c.get("delta")
        if delta is None:
            d = '<div class="d flat">&nbsp;</div>'
        else:
            kind = "up" if delta > 0.05 else "down" if delta < -0.05 else "flat"
            arrow = {"up": "▲", "down": "▼", "flat": "●"}[kind]
            d = f'<div class="d {kind}">{arrow} {abs(delta):.1f}{c.get("unit", "%")} vs prior month</div>'
        html.append(f'<div class="pbi-card" style="--c:{c["color"]}"><div class="t">{escape(c["label"])}</div>'
                    f'<div class="v">{escape(c["value"])}</div>{d}{sparkline_svg(c.get("spark", []), c["color"])}</div>')
    st.markdown(f'<div class="pbi-cards">{"".join(html)}</div>', unsafe_allow_html=True)


def panel_title(title: str, sub: str = "") -> None:
    st.markdown(f'<div class="panel-title">{escape(title)}</div>'
                + (f'<div class="panel-sub">{escape(sub)}</div>' if sub else ""), unsafe_allow_html=True)


def feature_tiles(tiles: list[tuple[str, str, str, str]]) -> None:
    cells = "".join(f'<div class="feature"><div class="ico">{ico}</div><div class="ft">{escape(title)}</div>'
                    f'<div class="fd">{escape(desc)}</div><span class="fk">{escape(key)}</span></div>'
                    for ico, title, desc, key in tiles)
    st.markdown(f'<div class="features">{cells}</div>', unsafe_allow_html=True)


def section(title: str, caption: str = "") -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>'
                + (f'<div class="section-caption">{escape(caption)}</div>' if caption else ""), unsafe_allow_html=True)


def pill(status: str) -> str:
    return f'<span class="pill {status}">{status}</span>'
