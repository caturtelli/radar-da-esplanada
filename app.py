import html
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
st.title('🏛️ Radar da Esplanada')
st.caption('Acompanhamento jornalístico da formação do governo federal')
base = Path(__file__).resolve().parent
if not (base / 'indicacoes.csv').exists():
    st.error('Arquivo indicacoes.csv não encontrado.'); st.stop()
df = pd.read_csv(base / 'indicacoes.csv', dtype=str, encoding='utf-8-sig').fillna('')
news_cols = ['indicacao_id','titulo','veiculo','jornalista','data_publicacao','url','tipo_evidencia','observacao']
if (base / 'noticias.csv').exists():
    news = pd.read_csv(base / 'noticias.csv', dtype=str, encoding='utf-8-sig').fillna('')
    for c in news_cols:
        if c not in news: news[c] = ''
else:
    news = pd.DataFrame(columns=news_cols)

def valid_url(u):
    try:
        p=urlparse(str(u).strip()); return p.scheme in ('https','http') and bool(p.netloc)
    except ValueError: return False

st.sidebar.header('Filtrar radar')
search = st.sidebar.text_input('Buscar nome ou cargo', placeholder='Digite para localizar...')
statuses = sorted(s for s in df['situacao'].unique() if s)
selected_statuses = st.sidebar.multiselect('Situação', statuses, default=statuses)
filtered = df[df['situacao'].isin(selected_statuses)].copy()
if search.strip():
    q=search.strip()
    filtered=filtered[filtered[['nome','cargo','ministerio']].apply(lambda c: c.str.contains(q, case=False, regex=False)).any(axis=1)]

m1,m2,m3,m4=st.columns(4)
m1.metric('Órgãos com registros',filtered['ministerio'].nunique())
m2.metric('Movimentações',len(filtered))
m3.metric('Pessoas citadas',filtered['nome'].nunique())
m4.metric('Reportagens vinculadas',len(news[news['indicacao_id'].isin(filtered['indicacao_id'])]))
st.divider()

if 'selected_ministry' not in st.session_state:
    st.session_state.selected_ministry = None
all_ministries=sorted(filtered['ministerio'].dropna().unique().tolist())
if st.session_state.selected_ministry not in all_ministries:
    st.session_state.selected_ministry = None

if st.session_state.selected_ministry is None:
    st.subheader('Ministérios e órgãos')
    st.caption('Selecione um cartão para consultar nomes cotados, situação e reportagens. São exibidos os órgãos cadastrados, não necessariamente todos os ministérios existentes.')
    if not all_ministries: st.info('Nenhum órgão encontrado com os filtros atuais.')
    for start in range(0,len(all_ministries),3):
        cols=st.columns(3)
        for col, ministry in zip(cols,all_ministries[start:start+3]):
            sub=filtered[filtered['ministerio']==ministry]
            n=len(news[news['indicacao_id'].isin(sub['indicacao_id'])])
            with col.container(border=True):
                st.markdown(f'#### {ministry}')
                st.caption(f'{sub["nome"].nunique()} pessoa(s) · {len(sub)} movimentação(ões) · {n} notícia(s)')
                if st.button('Ver indicações →',key=f'go_{ministry}',use_container_width=True):
                    st.session_state.selected_ministry=ministry
                    st.rerun()
else:
    ministry=st.session_state.selected_ministry
    if st.button('← Voltar a todos os ministérios'):
        st.session_state.selected_ministry=None
        st.rerun()
    st.subheader(ministry)
    sub=filtered[filtered['ministerio']==ministry].copy()
    st.caption(f'{sub["nome"].nunique()} pessoa(s) monitorada(s) · {len(sub)} movimentação(ões)')
    if sub.empty:
        st.info('Nenhum registro para este órgão com os filtros atuais.')
    else:
        st.markdown('### Visão comparativa')
        st.dataframe(sub[['nome','cargo','situacao','tipo_movimentacao']].rename(columns={'nome':'Nome','cargo':'Cargo','situacao':'Situação','tipo_movimentacao':'Movimentação'}),hide_index=True,use_container_width=True)
        st.markdown('### Detalhes e fontes')
        for _,item in sub.iterrows():
            related=news[news['indicacao_id']==item['indicacao_id']].drop_duplicates(subset=['indicacao_id','url']).sort_values('data_publicacao',ascending=False,kind='stable')
            with st.expander(f"{item['nome']} — {item['cargo']} · {len(related)} notícia(s)"):
                st.write('**Situação:**',item['situacao'])
                st.write('**Movimentação:**',item['tipo_movimentacao'])
                st.write('**Evidências favoráveis:**',item['evidencia_favoravel'] or 'Não cadastradas.')
                st.write('**Evidências contrárias:**',item['evidencia_contraria'] or 'Não cadastradas.')
                st.markdown('#### Reportagens relacionadas')
                if related.empty: st.info('Nenhuma reportagem cadastrada para esta indicação.')
                for ix,article in related.iterrows():
                    st.markdown(f"**{html.escape(article['titulo'] or 'Reportagem sem título')}**")
                    st.caption(' · '.join(x for x in [article['veiculo'],article['jornalista'],article['data_publicacao']] if x))
                    if article['tipo_evidencia']: st.write('**Tipo de evidência:**',article['tipo_evidencia'])
                    if article['observacao']: st.write(article['observacao'])
                    if valid_url(article['url']): st.link_button('Ler reportagem ↗',article['url'],key=f"article_{item['indicacao_id']}_{ix}")
                    else: st.warning('Link não cadastrado ou inválido.')
                    st.divider()

st.divider()
st.caption('O radar mostra apenas informações cadastradas. Menções jornalísticas não equivalem a nomeações confirmadas. A atualização automática será implementada em etapa posterior.')
