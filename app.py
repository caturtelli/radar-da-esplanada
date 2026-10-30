import html
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
st.title('🏛️ Radar da Esplanada')
st.caption('Acompanhamento jornalístico da formação do governo federal — primeiro e segundo escalões')

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


# Catálogo editorial: cada órgão pode ser incluído mesmo antes de haver uma indicação.
catalog_path = base / 'catalogo_orgaos.csv'
catalog_cols = ['orgao', 'categoria', 'orgao_superior']
if catalog_path.exists():
    catalog = pd.read_csv(catalog_path, dtype=str, encoding='utf-8-sig').fillna('')
    for c in catalog_cols:
        if c not in catalog.columns:
            catalog[c] = ''
else:
    catalog = pd.DataFrame(columns=catalog_cols)

def classify_level(cargo, orgao):
    """Classificação editorial inicial, revisável no CSV de indicações."""
    s = str(cargo).casefold().strip()
    if any(x in s for x in ['secretário-executivo', 'secretária-executiva',
                            'secretário nacional', 'secretária nacional',
                            'secretário de ', 'secretária de ',
                            'diretor', 'diretora', 'superintendente']):
        return 'Segundo escalão'
    if any(x in s for x in ['ministro', 'ministra', 'presidente', 'chefe de gabinete']):
        return 'Primeiro escalão / direção'
    return 'A classificar'

if 'escalao' not in df.columns:
    df['escalao'] = ''
df['escalao'] = df.apply(
    lambda row: row['escalao'].strip() or classify_level(row['cargo'], row['ministerio']), axis=1
)
# Catálogo não atribui nomes a cargos; apenas define a navegação.
registered = set(df['ministerio'].astype(str).str.strip()) - {''}
known = set(catalog['orgao'].astype(str).str.strip()) - {''}
missing = sorted(registered - known)
if missing:
    catalog = pd.concat([catalog, pd.DataFrame([
        {'orgao': o, 'categoria': 'Órgão com registros', 'orgao_superior': ''}
        for o in missing
    ])], ignore_index=True)
catalog = catalog.drop_duplicates(subset=['orgao'], keep='first')
org_names = catalog['orgao'].dropna().loc[lambda x: x.str.strip() != ''].tolist()

st.sidebar.header('Filtrar radar')
level_options = ['Primeiro escalão / direção', 'Segundo escalão', 'A classificar']
selected_levels = st.sidebar.multiselect('Escalão', level_options, default=level_options)

search = st.sidebar.text_input('Buscar nome ou cargo', placeholder='Digite para localizar...')
statuses = sorted(s for s in df['situacao'].unique() if s)
selected_statuses = st.sidebar.multiselect('Situação', statuses, default=statuses)
filtered = df[df['situacao'].isin(selected_statuses) & df['escalao'].isin(selected_levels)].copy()
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
show_empty = st.sidebar.checkbox('Mostrar órgãos sem indicações', value=True)
all_ministries = sorted(set(org_names) if show_empty else set(filtered['ministerio'].dropna().unique().tolist()))
if st.session_state.selected_ministry not in all_ministries:
    st.session_state.selected_ministry = None

if st.session_state.selected_ministry is None:
    st.subheader('Ministérios e órgãos')
    st.caption('Estrutura de referência editável; um cartão vazio não significa ausência de negociações.')
    cat_filter = st.selectbox('Categoria de órgão', ['Todas'] + sorted(set(catalog['categoria']) - {''}))
    if cat_filter != 'Todas':
        all_ministries = [o for o in all_ministries
                          if o in set(catalog.loc[catalog['categoria'] == cat_filter, 'orgao'])]
    st.caption('Selecione um cartão para consultar nomes cotados, situação e reportagens. São exibidos os órgãos cadastrados, não necessariamente todos os ministérios existentes.')
    if not all_ministries: st.info('Nenhum órgão encontrado com os filtros atuais.')
    for start in range(0,len(all_ministries),3):
        cols=st.columns(3)
        for col, ministry in zip(cols,all_ministries[start:start+3]):
            sub=filtered[filtered['ministerio']==ministry]
            n=len(news[news['indicacao_id'].isin(sub['indicacao_id'])])
            with col.container(border=True):
                st.markdown(f'#### {ministry}')
                superior = catalog.loc[catalog['orgao'] == ministry, 'orgao_superior']
                if not superior.empty and superior.iloc[0]:
                    st.caption(f'Vinculado a: {superior.iloc[0]}')
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
        st.caption('Classificação inicial automática por título do cargo; revise no campo escalao do CSV quando necessário.')
        st.dataframe(sub[['nome','cargo','escalao','situacao','tipo_movimentacao']].rename(columns={'nome':'Nome','cargo':'Cargo','escalao':'Escalão','situacao':'Situação','tipo_movimentacao':'Movimentação'}),hide_index=True,use_container_width=True)
        st.markdown('### Detalhes e fontes')
        for _,item in sub.iterrows():
            related=news[news['indicacao_id']==item['indicacao_id']].drop_duplicates(subset=['indicacao_id','url']).sort_values('data_publicacao',ascending=False,kind='stable')
            with st.expander(f"{item['nome']} — {item['cargo']} · {len(related)} notícia(s)"):
                st.write('**Escalão:**',item['escalao'])
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
st.caption('O catálogo é uma estrutura editorial editável, não uma lista oficial verificada. '
           'O radar mostra apenas informações cadastradas. Menções jornalísticas não equivalem a nomeações confirmadas. '
           'A atualização automática será implementada em etapa posterior.')

# Notícias coletadas são pistas para apuração, não evidências automaticamente validadas.
st.divider()
st.subheader('📰 Novas notícias para apuração')
coletadas_path = base / 'noticias_coletadas.csv'
status_path = base / 'status_coleta.json'
if status_path.exists():
    import json
    try:
        status = json.loads(status_path.read_text(encoding='utf-8'))
        st.caption(f"Última tentativa de coleta (UTC): {status.get('ultima_tentativa_utc', '—')} · "
                   f"Novas notícias: {status.get('novas_noticias', 0)} · "
                   f"Total: {status.get('total_armazenado', 0)}")
        if status.get('falhas'):
            st.warning(f"Algumas buscas falharam ({len(status['falhas'])}). Consulte o log do GitHub Actions.")
    except (ValueError, OSError):
        st.warning('Status da coleta indisponível.')
if coletadas_path.exists():
    coletadas = pd.read_csv(coletadas_path, dtype=str, encoding='utf-8-sig').fillna('')
    st.caption('Resultados de RSS agregados, sujeitos a falsos positivos. A menção de um nome não confirma indicação.')
    q = st.text_input('Filtrar notícias coletadas por nome, cargo ou termo', key='busca_coleta')
    if q.strip():
        coletadas = coletadas[coletadas[['titulo','veiculo','nomes_mencionados','busca']].apply(
            lambda col: col.str.contains(q.strip(), case=False, regex=False)).any(axis=1)]
    st.write(f'{len(coletadas)} resultado(s)')
    for ix, artigo in coletadas.head(100).iterrows():
        with st.container(border=True):
            st.markdown(f"**{html.escape(artigo['titulo'])}**")
            st.caption(f"{artigo['veiculo']} · {artigo['data_publicacao']} · Menções: {artigo['nomes_mencionados'] or 'não identificadas'}")
            if valid_url(artigo['url']):
                st.link_button('Abrir notícia ↗', artigo['url'], key=f'coleta_{ix}')
else:
    st.info('A primeira coleta ainda não foi executada. No GitHub, abra Actions → Atualizar Radar da Esplanada → Run workflow.')
