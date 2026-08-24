"""Estilos institucionales centralizados."""

import streamlit as st

from config.settings import COLORS


def apply_global_styles() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --tp-primary: {COLORS['primary']};
            --tp-dark: {COLORS['primary_dark']};
            --tp-navy: {COLORS['navy']};
            --tp-bg: {COLORS['background']};
            --tp-border: {COLORS['border']};
        }}
        .stApp {{ background: var(--tp-bg); }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #00304D 0%, #004662 100%);
        }}
        [data-testid="stSidebar"] * {{ color: white; }}
        [data-testid="stSidebar"] [data-testid="stImage"] {{
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            margin: .25rem 0 1.15rem;
            padding: 1rem;
            border-radius: 14px;
            background: white;
            box-shadow: 0 4px 14px rgba(0, 0, 0, .14);
        }}
        [data-testid="stSidebar"] [data-testid="stImage"] img {{
            display: block;
            margin: 0 auto;
            object-fit: contain;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            width: 100%; text-align: left; border: 0; border-radius: 9px;
            background: rgba(255,255,255,.07); padding: .55rem .75rem;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: {COLORS['primary']}; color: white;
        }}
        [data-testid="stSidebar"] details {{
            border: 1px solid rgba(255,255,255,.12); border-radius: 10px;
            background: rgba(255,255,255,.04); padding: .15rem .5rem;
        }}
        .tp-project-bar {{
            display:grid; grid-template-columns: minmax(180px, 1.5fr) repeat(3, minmax(130px, 1fr));
            gap: 1rem; align-items:center; padding: .9rem 1rem; margin-bottom: 1.2rem; border-radius: 12px;
            background: white; border-left: 5px solid var(--tp-primary);
            box-shadow: 0 2px 12px rgba(0,48,77,.07);
        }}
        .tp-project-main, .tp-project-detail {{ display:flex; flex-direction:column; gap:.2rem; }}
        .tp-project-main strong {{ color:var(--tp-navy); font-size:1.05rem; }}
        .tp-project-bar small {{ color:{COLORS['muted']}; font-size:.7rem; font-weight:700; letter-spacing:.04em; }}
        .tp-project-detail span {{ color:{COLORS['text']}; font-size:.9rem; }}
        .tp-card {{
            min-height: 120px; padding: 1.15rem; border-radius: 14px;
            background: white; border: 1px solid var(--tp-border);
            box-shadow: 0 3px 14px rgba(0,48,77,.06);
        }}
        .tp-card-label {{ color: {COLORS['muted']}; font-size: .9rem; }}
        .tp-card-value {{ color: var(--tp-navy); font-size: 1.75rem; font-weight: 700; }}
        .tp-empty {{
            padding: 2rem; text-align:center; border-radius:14px;
            background:white; border:1px dashed #AFC3B8;
        }}
        h1, h2, h3 {{ color: var(--tp-navy); }}
        .stButton > button[kind="primary"] {{
            background: var(--tp-primary); border-color: var(--tp-primary);
        }}
        @media (max-width: 900px) {{
            .tp-project-bar {{ grid-template-columns: 1fr 1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
