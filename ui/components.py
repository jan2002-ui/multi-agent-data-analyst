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


def section(title: str, caption: str = "") -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>'
                + (f'<div class="section-caption">{escape(caption)}</div>' if caption else ""), unsafe_allow_html=True)


def pill(status: str) -> str:
    return f'<span class="pill {status}">{status}</span>'
