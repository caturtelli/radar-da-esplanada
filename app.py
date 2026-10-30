import streamlit as st
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
st.title('🏛️ Radar da Esplanada')
st.caption('Monitoramento de indicações, nomeações e permanências no governo federal')

pasta = Path(__file__).resolve().parent
arquivo = pasta / 'indicacoes.csv'
arquivo_noticias = pasta / 'noticias.csv'
if not arquivo.exists():
    st.error('Cadastro de indicações não encontrado.')
    st.stop()

df = pd.read_csv(arquivo, dtype=str, encoding='utf-8-sig').fillna('')
if 'indicacao_id' not in df.columns:
    st.error('A coluna indicacao_id não foi encontrada em indicacoes.csv.')
    st.stop()

colunas_noticias = ['indicacao_id', 'titulo', 'veiculo', 'jornalista', 'data_publicacao', 'url', 'tipo_evidencia', 'observacao']
if arquivo_noticias.exists():
    noticias = pd.read_csv(arquivo_noticias, dtype=str, encoding='utf-8-sig').fillna('')
    for coluna in colunas_noticias:
        if coluna not in noticias.columns:
            noticias[coluna] = ''
else:
    noticias = pd.DataFrame(columns=colunas_noticias)

def url_valida(url):
    try:
        p = urlparse(str(url).strip())
        return p.scheme in ('https', 'http') and bool(p.netloc)
    except ValueError:
        return False

st.sidebar.header('Filtros')
ministerios = sorted(df['ministerio'].unique().tolist())
ministerios_selecionados = st.sidebar.multiselect('Ministérios e órgãos', ministerios, default=ministerios)
situacoes = sorted(df['situacao'].unique().tolist())
situacoes_selecionadas = st.sidebar.multiselect('Situação', situacoes, default=situacoes)
busca = st.sidebar.text_input('Buscar pessoa ou cargo')
filtrado = df[df['ministerio'].isin(ministerios_selecionados) & df['situacao'].isin(situacoes_selecionadas)].copy()
if busca:
    filtrado = filtrado[
        filtrado['nome'].str.contains(busca, case=False, na=False, regex=False)
        | filtrado['cargo'].str.contains(busca, case=False, na=False, regex=False)
    ]

c1, c2, c3, c4 = st.columns(4)
c1.metric('Movimentações monitoradas', len(filtrado))
c2.metric('Pessoas', filtrado['nome'].nunique())
c3.metric('Ministérios e órgãos', filtrado['ministerio'].nunique())
c4.metric('Reportagens vinculadas', len(noticias[noticias['indicacao_id'].isin(filtrado['indicacao_id'])]))
st.divider()
st.subheader('Indicações em acompanhamento')

if filtrado.empty:
    st.info('Nenhuma movimentação encontrada com esses filtros.')
else:
    for _, item in filtrado.iterrows():
        relacionadas = noticias[noticias['indicacao_id'] == item['indicacao_id']].copy()
        relacionadas = relacionadas.drop_duplicates(subset=['indicacao_id', 'url'])
        relacionadas = relacionadas.sort_values('data_publicacao', ascending=False, kind='stable')
        with st.expander(f"{item['nome']} — {item['cargo']} · {len(relacionadas)} notícia(s)"):
            st.write('**Ministério/órgão:**', item['ministerio'])
            st.write('**Movimentação:**', item['tipo_movimentacao'])
            st.write('**Situação:**', item['situacao'])
            st.markdown('#### Evidências favoráveis')
            st.write(item['evidencia_favoravel'] or 'Ainda não registradas.')
            st.markdown('#### Evidências contrárias')
            st.write(item['evidencia_contraria'] or 'Ainda não registradas.')
            st.markdown(f"#### Notícias e fontes ({len(relacionadas)})")
            if relacionadas.empty:
                st.info('Ainda não há reportagens vinculadas a esta indicação.')
            else:
                for _, noticia in relacionadas.iterrows():
                    titulo = noticia['titulo'] or 'Reportagem sem título cadastrado'
                    meta = ' · '.join(p for p in [noticia['veiculo'], noticia['jornalista'], noticia['data_publicacao']] if p)
                    st.markdown(f'**{titulo}**')
                    if meta:
                        st.caption(meta)
                    if noticia['tipo_evidencia']:
                        st.write('**Relação com a indicação:**', noticia['tipo_evidencia'])
                    if noticia['observacao']:
                        st.write(noticia['observacao'])
                    if url_valida(noticia['url']):
                        st.link_button('Ler reportagem ↗', noticia['url'], key=f"link_{item['indicacao_id']}_{_}")
                    else:
                        st.warning('Link ausente ou inválido.')
                    st.divider()

st.caption('O Radar reúne informações jornalísticas em apuração. Citações no noticiário não equivalem a nomeações confirmadas. A biblioteca exibe notícias cadastradas, não uma busca em tempo real.')
