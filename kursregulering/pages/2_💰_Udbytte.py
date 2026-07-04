"""
Streamlit-side: Beregning af udbytte (bruttoudbytte og kildeskat).

Binder udbytte.py (parsing, validering, beregning) og csv_eksport.py
(genbruger samme kassekladde-format som kursregulerings-siden) sammen.

Hvert trin er pakket i sit eget "kort" (st.container(border=True)) for at
gøre siden roligere at se på og tydeliggøre, hvor man er i flowet.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from csv_eksport import byg_udbytte_kassekladde_linjer, generer_csv, linjer_til_dataframe
from udbytte import (
    beregn_alle_udbytter,
    fund_til_dataframe,
    har_fejl,
    indlaes_udbytte_excel,
    opsummering,
    resultater_til_dataframe,
    valider_udbytte,
)

st.set_page_config(page_title="Udbytte", page_icon="💰", layout="wide")
st.title("💰 Udbytte")
st.caption(
    "Regner ud, hvor meget der egentlig blev udloddet i udbytte (bruttobeløbet), "
    "før landet trak skat, ud fra det beløb der endte på jeres bankkonto."
)
st.write("")

# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.header("1️⃣ Upload jeres udbytteliste")
    st.caption("Én linje pr. udbyttebetaling: papirnavn, land, dato og det beløb I fik ind på bankkontoen.")
    uploaded = st.file_uploader("Vælg Excel-fil", type=["xlsx", "xls"], key="udbytte_upload")

    if uploaded is None:
        st.info("Upload en Excel-fil for at komme i gang. Der ligger et eksempel i `test_data/eksempel_udbytte.xlsx`.")
        st.stop()

    parse_resultat = indlaes_udbytte_excel(uploaded)

    if not parse_resultat.er_gyldig:
        st.error("Filen kunne ikke læses korrekt:")
        for fejl in parse_resultat.kritiske_fejl:
            st.error(f"- {fejl}")
        st.stop()

    for besked in parse_resultat.info:
        st.info(besked)

data = parse_resultat.data
st.write("")

# ---------------------------------------------------------------------------
# 2. Validering
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.header("2️⃣ Tjek af data")
    fund = valider_udbytte(data)
    detaljer = fund_til_dataframe(fund)

    if detaljer.empty:
        st.success("✅ Alt ser fint ud — ingen fejl eller advarsler.")
    else:
        st.dataframe(detaljer, hide_index=True, use_container_width=True)

    blokeret = har_fejl(fund)
    if blokeret:
        st.error("🚫 Der er mindst én fejl, der skal rettes først. Ret filen og upload den igen.")
    elif not detaljer.empty:
        st.warning("Der er kun advarsler — I kan godt regne videre, men kig lige på dem først.")

st.write("")

# ---------------------------------------------------------------------------
# 3. Beregning
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.header("3️⃣ Beregn bruttoudbytte og kildeskat")
    st.caption(
        "Kort fortalt: I har fået et nettobeløb ind på kontoen. Vi 'ganger det op' med den kendte "
        "skattesats for landet, så I kan se, hvad det oprindelige (brutto) udbytte var, og hvor "
        "meget der blev trukket i skat undervejs."
    )

    kan_beregne = st.button("Beregn", type="primary", disabled=blokeret, key="udbytte_beregn")

    if kan_beregne:
        st.session_state["udbytte_resultater"] = beregn_alle_udbytter(data)

    resultater = st.session_state.get("udbytte_resultater")

    if resultater:
        resultat_df = resultater_til_dataframe(resultater)
        st.dataframe(resultat_df, hide_index=True, use_container_width=True)

        total = opsummering(resultater)
        kol1, kol2, kol3 = st.columns(3)
        kol1.metric("Dansk udbytte, brutto", f"{total['dansk_brutto']:,.2f} kr.".replace(",", "."))
        kol2.metric("Udenlandsk udbytte, brutto", f"{total['udenlandsk_brutto']:,.2f} kr.".replace(",", "."))
        kol3.metric("I alt modtaget (netto)", f"{total['netto_i_alt']:,.2f} kr.".replace(",", "."))

if resultater:
    st.write("")
    # -----------------------------------------------------------------------
    # 4. CSV-eksport
    # -----------------------------------------------------------------------
    with st.container(border=True):
        st.header("4️⃣ Hent fil til e-conomic")
        st.caption(
            "Bruttoudbyttet bogføres som indtægt. Kildeskatten bogføres som et tilgodehavende "
            "(I forventer at få den tilbage). Nettobeløbet er det, der allerede står på jeres bankkonto."
        )

        col1, col2 = st.columns(2)
        with col1:
            resultatkonto = st.text_input("Konto til udbytteindtægt", value="2100", key="udb_resultatkonto")
            bankkonto = st.text_input("Bankkonto", value="5820", key="udb_bankkonto")
            bilagstype = st.text_input("Bilagstype", value="Finansbilag", key="udb_bilagstype")
        with col2:
            dansk_skattekonto = st.text_input("Konto til tilgodehavende dansk udbytteskat", value="6210", key="udb_dk_skat")
            udenlandsk_skattekonto = st.text_input("Konto til tilgodehavende udenlandsk udbytteskat", value="6220", key="udb_udl_skat")
            start_bilagsnummer = st.number_input("Start bilagsnummer", min_value=1, value=1, step=1, key="udb_bilagsnr")

        if all([resultatkonto, bankkonto, dansk_skattekonto, udenlandsk_skattekonto]):
            linjer = byg_udbytte_kassekladde_linjer(
                resultater,
                resultatkonto=resultatkonto,
                bankkonto=bankkonto,
                dansk_skattekonto=dansk_skattekonto,
                udenlandsk_skattekonto=udenlandsk_skattekonto,
                bilagstype=bilagstype,
                start_bilagsnummer=int(start_bilagsnummer),
            )

            st.subheader("Sådan kommer filen til at se ud")
            st.dataframe(linjer_til_dataframe(linjer), hide_index=True, use_container_width=True)

            csv_tekst = generer_csv(linjer)
            st.download_button(
                "⬇️ Download CSV til e-conomic",
                data=csv_tekst.encode("utf-8"),
                file_name="udbytte_kassekladde.csv",
                mime="text/csv",
                type="primary",
            )
        else:
            st.info("Udfyld de fire kontonumre for at kunne hente filen.")
