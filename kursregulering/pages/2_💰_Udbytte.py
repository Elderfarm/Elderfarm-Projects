"""
Streamlit-side: Beregning af udbytte (bruttoudbytte og kildeskat).

Hovedvejen er direkte indtastning i en tabel (st.data_editor). Har man
mange linjer, kan man i stedet uploade en Excel- eller CSV-fil, som
udfylder tabellen automatisk — man kan stadig rette i den bagefter.

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
    LANDE_NAVNE,
    beregn_alle_udbytter,
    eksempel_indtastningsraekke,
    fra_indtastningstabel,
    fund_til_dataframe,
    har_fejl,
    indlaes_udbytte_fil,
    opsummering,
    resultater_til_dataframe,
    til_indtastningstabel,
    valider_udbytte,
)

st.set_page_config(page_title="Udbytte", page_icon="💰", layout="wide")
st.title("💰 Udbytte")
st.caption(
    "Regner ud, hvor meget der egentlig blev udloddet i udbytte (bruttobeløbet) og hvor meget "
    "der blev trukket i skat, uanset om I kender netto- eller bruttobeløbet."
)
st.write("")


def _raekke_er_udfyldt(raekke: pd.Series) -> bool:
    papir = str(raekke.get("Papir") or "").strip()
    beloeb = raekke.get("Beløb (kr.)")
    return bool(papir) or pd.notna(beloeb)


if "udbytte_tabel" not in st.session_state:
    st.session_state.udbytte_tabel = eksempel_indtastningsraekke()
if "udbytte_upload_signatur" not in st.session_state:
    st.session_state.udbytte_upload_signatur = None
if "udbytte_editor_version" not in st.session_state:
    st.session_state.udbytte_editor_version = 0

# ---------------------------------------------------------------------------
# 1. Indtast eller upload
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.header("1️⃣ Indtast jeres udbytter")
    st.caption(
        "Skriv direkte i tabellen nedenfor — én linje pr. udbyttebetaling. I kan angive ENTEN "
        "netto- eller bruttobeløbet, alt efter hvad I kender. Tryk på + for at tilføje flere linjer."
    )

    land_muligheder = sorted(set(LANDE_NAVNE.values()) | set(st.session_state.udbytte_tabel["Land"].dropna()))

    redigeret = st.data_editor(
        st.session_state.udbytte_tabel,
        num_rows="dynamic",
        use_container_width=True,
        key=f"udbytte_editor_{st.session_state.udbytte_editor_version}",
        column_config={
            "Papir": st.column_config.TextColumn("Papir", required=True),
            "Land": st.column_config.SelectboxColumn("Land", options=land_muligheder, required=True),
            "Type": st.column_config.SelectboxColumn("Type", options=["Netto", "Brutto"], required=True),
            "Beløb (kr.)": st.column_config.NumberColumn("Beløb (kr.)", format="%.2f", min_value=0.0),
            "Dato": st.column_config.DateColumn("Dato", format="DD-MM-YYYY"),
        },
    )

    with st.expander("Har du mange linjer? Upload en Excel- eller CSV-fil i stedet"):
        st.caption(
            "Filen udfylder tabellen ovenfor automatisk — I kan stadig rette i den bagefter. "
            "Eksempler ligger i `test_data/eksempel_udbytte.xlsx` og `.csv`."
        )
        uploaded = st.file_uploader("Vælg fil", type=["xlsx", "xls", "csv"], key="udbytte_upload")

        if uploaded is not None:
            signatur = (uploaded.name, uploaded.size)
            if signatur != st.session_state.udbytte_upload_signatur:
                parse_resultat = indlaes_udbytte_fil(uploaded, uploaded.name)
                if not parse_resultat.er_gyldig:
                    st.error("Filen kunne ikke læses korrekt:")
                    for fejl in parse_resultat.kritiske_fejl:
                        st.error(f"- {fejl}")
                else:
                    for besked in parse_resultat.info:
                        st.info(besked)
                    st.session_state.udbytte_tabel = til_indtastningstabel(parse_resultat.data)
                    st.session_state.udbytte_upload_signatur = signatur
                    st.session_state.udbytte_editor_version += 1
                    st.rerun()

data = fra_indtastningstabel(redigeret[redigeret.apply(_raekke_er_udfyldt, axis=1)].reset_index(drop=True))

if data.empty:
    st.info("Tilføj mindst én linje i tabellen for at komme videre.")
    st.stop()

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
        st.error("🚫 Der er mindst én fejl, der skal rettes først. Ret i tabellen ovenfor.")
    elif not detaljer.empty:
        st.warning("Der er kun advarsler — I kan godt regne videre, men kig lige på dem først.")

st.write("")

# ---------------------------------------------------------------------------
# 3. Beregning
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.header("3️⃣ Beregn bruttoudbytte og kildeskat")
    st.caption(
        "Kort fortalt: kender I nettobeløbet, 'ganger vi det op' til bruttobeløbet — og omvendt, "
        "hvis I kender bruttobeløbet — ud fra den kendte skattesats for landet."
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
            "(dansk kildeskat kan modregnes/tilbagesøges i Danmark, hjemlandet — udenlandsk kildeskat "
            "kræver typisk en separat tilbagesøgning). Nettobeløbet er det, der allerede står på "
            "jeres bankkonto."
        )

        col1, col2 = st.columns(2)
        with col1:
            resultatkonto = st.text_input("Konto til udbytteindtægt (drift)", value="2100", key="udb_resultatkonto")
            bankkonto = st.text_input("Bankkonto", value="5820", key="udb_bankkonto")
            bilagstype = st.text_input("Bilagstype", value="Finansbilag", key="udb_bilagstype")
        with col2:
            dansk_skattekonto = st.text_input("Konto til tilgodehavende udbytteskat, Danmark", value="6210", key="udb_dk_skat")
            udenlandsk_skattekonto = st.text_input("Konto til tilgodehavende udbytteskat, udenlandsk", value="6220", key="udb_udl_skat")
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
