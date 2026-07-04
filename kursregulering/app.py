"""
Forside for værktøjet. De to rigtige sider ligger i mappen `pages/` og
findes automatisk af Streamlit i menuen til venstre.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Aktier & Udbytte", page_icon="💹", layout="wide")

st.title("💹 Aktier & Udbytte")
st.write("Hvad vil du gerne regne på i dag? Klik på en af de to knapper nedenfor.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Kursregulering")
    st.write("Har jeres aktier vundet eller tabt værdi i år? Beregn skattemæssig gevinst/tab.")
    st.page_link("pages/1_📈_Kursregulering.py", label="Gå til Kursregulering", icon="📈")

with col2:
    st.subheader("💰 Udbytte")
    st.write("Har I fået udbytte fra jeres aktier? Beregn bruttobeløb og kildeskat.")
    st.page_link("pages/2_💰_Udbytte.py", label="Gå til Udbytte", icon="💰")

st.divider()
st.caption("Begge værktøjer virker helt for sig selv — I kan bruge det ene uden det andet.")
