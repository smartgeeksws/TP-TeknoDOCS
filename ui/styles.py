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
            --tp-purple: {COLORS['purple']};
            --tp-cyan: {COLORS['cyan']};
            --tp-yellow: {COLORS['yellow']};
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
        [class*="st-key-project-card-"] {{
            position: relative;
            overflow: hidden;
            margin: .8rem 0 1.2rem;
            padding: 1.35rem 1.4rem;
            border: 1px solid rgba(0, 120, 50, .18);
            border-radius: 18px;
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FCF9 100%);
            box-shadow: 0 10px 28px rgba(0, 48, 77, .11);
            transition: transform .18s ease, box-shadow .18s ease;
        }}
        [class*="st-key-project-card-"]::before {{
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 6px;
            background: linear-gradient(180deg, var(--tp-primary), var(--tp-dark));
        }}
        [class*="st-key-project-card-"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 15px 34px rgba(0, 48, 77, .16);
        }}
        [class*="st-key-project-card-"] h3 {{
            margin-bottom: .35rem;
            color: var(--tp-navy);
        }}
        [class*="st-key-select-project-"] button {{
            min-height: 2.65rem;
            border: 1px solid var(--tp-primary) !important;
            background: linear-gradient(135deg, var(--tp-primary), var(--tp-dark)) !important;
            color: white !important;
            font-weight: 700 !important;
            box-shadow: 0 5px 13px rgba(57, 169, 0, .24);
        }}
        [class*="st-key-select-project-"] button:hover:not(:disabled) {{
            filter: brightness(.95);
            transform: translateY(-1px);
        }}
        [class*="st-key-select-project-"] button:disabled {{
            opacity: .72;
            box-shadow: none;
        }}
        [class*="st-key-edit-project-"] button {{
            min-height: 2.65rem;
            border: 1px solid var(--tp-navy) !important;
            background: var(--tp-navy) !important;
            color: white !important;
            font-weight: 650 !important;
            box-shadow: 0 5px 13px rgba(0, 48, 77, .2);
        }}
        [class*="st-key-edit-project-"] button:hover {{
            background: #004B70 !important;
            color: white !important;
        }}
        [class*="st-key-delete-project-"] button {{
            min-height: 2.65rem;
            border: 1px solid var(--tp-purple) !important;
            background: #FFFFFF !important;
            color: var(--tp-purple) !important;
            font-weight: 650 !important;
        }}
        [class*="st-key-delete-project-"] button:hover {{
            background: var(--tp-purple) !important;
            color: white !important;
            box-shadow: 0 5px 13px rgba(113, 39, 122, .2);
        }}
        [class*="st-key-phase-card-"] {{
            min-height: 220px;
            margin: .6rem 0;
            padding: 1.2rem;
            border: 1px solid var(--tp-border);
            border-top: 5px solid var(--tp-primary);
            border-radius: 16px;
            background: #FFFFFF;
            box-shadow: 0 8px 24px rgba(0, 48, 77, .09);
        }}
        .st-key-phase-card-planeacion {{ border-top-color: var(--tp-purple); }}
        .st-key-phase-card-ejecucion {{ border-top-color: var(--tp-navy); }}
        .st-key-phase-card-cierre {{ border-top-color: var(--tp-yellow); }}        [class*="st-key-phase-card-"] h3 {{
            color: var(--tp-navy);
            font-size: 1.1rem;
        }}
        [class*="st-key-dashboard-phase-"] button {{
            border-color: var(--tp-dark) !important;
            color: var(--tp-dark) !important;
            font-weight: 700 !important;
        }}
        [class*="st-key-dashboard-phase-"] button:hover {{
            background: var(--tp-dark) !important;
            color: #FFFFFF !important;
        }}
        [class*="st-key-dashboard-document-"] button {{
            justify-content: flex-start;
            color: var(--tp-navy) !important;
            font-weight: 600 !important;
        }}
        [class*="st-key-dashboard-document-"] button:hover {{
            background: rgba(80, 229, 249, .16) !important;
            color: var(--tp-navy) !important;
        }}
        @media (max-width: 900px) {{
            .tp-project-bar {{ grid-template-columns: 1fr 1fr; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
