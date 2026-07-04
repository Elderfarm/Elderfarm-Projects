"""
Forside for værktøjet. De to rigtige sider ligger i mappen `pages/` og
findes automatisk af Streamlit i menuen til venstre.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Aktier & Udbytte", page_icon="💹", layout="centered")

st.markdown(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<h1 style='text-align:center; margin-bottom:0;'>💹 Aktier & Udbytte</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center; font-size:1.1rem; color:gray; margin-top:0;'>"
    "Hvad vil du gerne regne på i dag?</p>",
    unsafe_allow_html=True,
)
st.write("")

col1, col2 = st.columns(2, gap="medium")

with col1:
    with st.container(border=True):
        st.markdown("<div style='text-align:center; font-size:3rem;'>📈</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;'>Kursregulering</h3>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:gray;'>Har jeres aktier vundet eller tabt værdi i år? "
            "Beregn skattemæssig gevinst/tab.</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_📈_Kursregulering.py", label="Gå til Kursregulering →", icon="📈", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("<div style='text-align:center; font-size:3rem;'>💰</div>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center;'>Udbytte</h3>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center; color:gray;'>Har I fået udbytte fra jeres aktier? "
            "Beregn bruttobeløb og kildeskat.</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_💰_Udbytte.py", label="Gå til Udbytte →", icon="💰", use_container_width=True)

st.write("")
st.markdown(
    "<p style='text-align:center; color:gray; font-size:0.9rem;'>"
    "Begge værktøjer virker helt for sig selv — brug det ene uden det andet.</p>",
    unsafe_allow_html=True,
)
