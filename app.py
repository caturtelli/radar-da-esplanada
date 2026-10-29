
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Radar da Esplanada",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Radar da Esplanada")
st.caption(
    "Monitoramento de indicações, nomeações e permanências "
    "no governo federal"
)

pasta = Path(__file__).resolve().parent
arquivo = pasta / "indicacoes.csv"

if not arquivo.exists():
    st.error("Cadastro de indicações não encontrado.")
    st.stop()

df = pd.read_csv(arquivo).fillna("")

st.sidebar.header("Filtros")

ministerios = sorted(df["ministerio"].unique().tolist())

ministerios_selecionados = st.sidebar.multiselect(
    "Ministérios e órgãos",
    options=ministerios,
    default=ministerios
)

situacoes = sorted(df["situacao"].unique().tolist())

situacoes_selecionadas = st.sidebar.multiselect(
    "Situação",
    options=situacoes,
    default=situacoes
)

busca = st.sidebar.text_input(
    "Buscar pessoa ou cargo"
)

filtrado = df[
    df["ministerio"].isin(ministerios_selecionados)
    & df["situacao"].isin(situacoes_selecionadas)
].copy()

if busca:
    filtro_busca = (
        filtrado["nome"].str.contains(
            busca, case=False, na=False, regex=False
        )
        | filtrado["cargo"].str.contains(
            busca, case=False, na=False, regex=False
        )
    )
    filtrado = filtrado[filtro_busca]

col1, col2, col3 = st.columns(3)

col1.metric("Movimentações monitoradas", len(filtrado))
col2.metric("Pessoas", filtrado["nome"].nunique())
col3.metric("Ministérios e órgãos", filtrado["ministerio"].nunique())

st.divider()

st.subheader("Indicações em acompanhamento")

if filtrado.empty:
    st.info("Nenhuma movimentação encontrada com esses filtros.")
else:
    for _, item in filtrado.iterrows():

        titulo = (
            f"{item['nome']} — {item['cargo']}"
        )

        with st.expander(titulo):

            st.write("**Ministério/órgão:**", item["ministerio"])
            st.write("**Movimentação:**", item["tipo_movimentacao"])
            st.write("**Situação:**", item["situacao"])

            st.markdown("#### Evidências favoráveis")
            st.write(
                item["evidencia_favoravel"]
                or "Ainda não registradas."
            )

            st.markdown("#### Evidências contrárias")
            st.write(
                item["evidencia_contraria"]
                or "Ainda não registradas."
            )

            if item["autor_verificado"]:
                st.write(
                    "**Jornalista:**",
                    item["autor_verificado"]
                )

            if str(item["fonte_verificada"]).startswith(
                ("https://", "http://")
            ):
                st.link_button(
                    "Abrir reportagem",
                    item["fonte_verificada"]
                )

st.divider()

st.caption(
    "O Radar reúne informações jornalísticas em apuração. "
    "Citações no noticiário não equivalem a nomeações confirmadas."
)
