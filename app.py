import html
import json
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st
from classificar_noticias import associate

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
st.markdown("""<style>
.stApp {background:#f5f7fb;color:#17243b}
.block-container {padding-top:1.6rem;max-width:1480px}
h1,h2,h3 {color:#142b4b!important;letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;padding:18px;border-radius:14px;border:1px solid #dce4ed;box-shadow:0 2px 10px #142b4b08}
[data-testid="stVerticalBlockBorderWrapper"] {background:white;border-radius:16px;border-color:#dce4ed!important}
.stButton button {border-radius:10px;font-weight:600}
.radar-eyebrow {font-size:.8rem;letter-spacing:.13em;color:#4b698e;font-weight:700}
.radar-title {font-size:2.6rem;font-weight:800;color:#142b4b;line-height:1.2;margin:.25rem 0}
.radar-subtitle {color:#5e7087;margin-bottom:1.2rem}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="radar-eyebrow">INTELIGÊNCIA JORNALÍSTICA · BRASÍLIA</div><div class="radar-title">🏛️ Radar da Esplanada</div><div class="radar-subtitle">Formação do governo federal · primeiro e segundo escalões</div>',unsafe_allow_html=True)
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

collected_path = base / 'noticias_coletadas.csv'
if collected_path.exists():
    try:
        collected = pd.read_csv(collected_path, dtype=str, encoding='utf-8-sig').fillna('')
    except (ValueError, pd.errors.EmptyDataError, UnicodeError) as exc:
        st.warning(f'Não foi possível ler notícias coletadas: {exc}')
        collected = pd.DataFrame()
else:
    collected = pd.DataFrame()
status_path = base / 'status_coleta.json'
status = {}
if status_path.exists():
    try:
        status = json.loads(status_path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        status = {}

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

# Associação calculada em cada leitura: novas notícias entram sem alterar o coletor.
if not collected.empty and 'titulo' in collected.columns:
    collected['orgaos_associados'] = collected['titulo'].map(
        lambda title: associate(title, org_names))
    collected['qtd_orgaos'] = collected['orgaos_associados'].map(len)
else:
    collected['orgaos_associados'] = pd.Series(dtype=object)
    collected['qtd_orgaos'] = pd.Series(dtype=int)

st.sidebar.header('Navegação')
view = st.sidebar.radio('Visualizar', ['Ministérios', 'Notícias coletadas'], index=0)
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
m1.metric('Órgãos no catálogo',len(catalog))
m2.metric('Pessoas citadas',filtered['nome'].nunique())
m3.metric('Notícias coletadas',len(collected))
m4.metric('Última coleta (UTC)', str(status.get('ultima_tentativa_utc','Sem registro'))[11:16])
st.divider()

if 'selected_ministry' not in st.session_state:
    st.session_state.selected_ministry = None
show_empty = st.sidebar.checkbox('Mostrar órgãos sem indicações', value=True)
all_ministries = sorted(set(org_names) if show_empty else set(filtered['ministerio'].dropna().unique().tolist()))
if st.session_state.selected_ministry not in all_ministries:
    st.session_state.selected_ministry = None

if view == 'Notícias coletadas':
    st.subheader('Últimas notícias coletadas')
    st.caption('Associações automáticas baseadas apenas nas manchetes, sem confirmação de nomeações.')
    only_associated = st.checkbox('Mostrar apenas notícias associadas a algum órgão', value=False)
    if collected.empty:
        st.info('Nenhuma notícia automática encontrada neste pacote. A coleta continua sendo responsabilidade do workflow existente.')
    else:
        date_candidates = [c for c in ['data_publicacao','publicado_em','published','data'] if c in collected.columns]
        display = collected[collected['qtd_orgaos'] > 0].copy() if only_associated else collected.copy()
        display['Órgãos sugeridos'] = display['orgaos_associados'].map(lambda v: '; '.join(v))
        display['_data'] = pd.to_datetime(display['data_publicacao'], errors='coerce', utc=True)
        display = display.sort_values('_data', ascending=False, kind='stable')
        cols = [c for c in ['titulo','veiculo','data_publicacao','Órgãos sugeridos','url'] if c in display.columns]
        st.dataframe(display[cols].head(500), hide_index=True, use_container_width=True,
                     column_config={'url': st.column_config.LinkColumn('Ler reportagem')})
elif st.session_state.selected_ministry is None:
    st.subheader('Ministérios e órgãos')
    st.caption('Estrutura de referência editável; um cartão vazio não significa ausência de negociações.')
    cat_filter = st.selectbox('Categoria de órgão', ['Ministério', 'Todas'] + sorted(set(catalog['categoria']) - {'', 'Ministério'}))
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
            auto_n = int(collected['orgaos_associados'].map(lambda v: ministry in v).sum()) if not collected.empty else 0
            with col.container(border=True):
                st.markdown(f'#### {ministry}')
                superior = catalog.loc[catalog['orgao'] == ministry, 'orgao_superior']
                if not superior.empty and superior.iloc[0]:
                    st.caption(f'Vinculado a: {superior.iloc[0]}')
                st.caption(f'{sub["nome"].nunique()} pessoa(s) cadastrada(s) · {n} fonte(s) verificadas')
                st.caption(f'📰 {auto_n} notícia(s) associada(s) automaticamente · não verificadas')
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
    auto_related = collected[collected['orgaos_associados'].map(lambda v: ministry in v)].copy() if not collected.empty else collected.copy()
    st.markdown('### Notícias associadas automaticamente')
    st.caption('Triagem por manchete. Pode conter falsos positivos; não equivale a indicação confirmada.')
    if auto_related.empty:
        st.info('Nenhuma notícia associada automaticamente a este órgão.')
    else:
        auto_related['_data'] = pd.to_datetime(auto_related['data_publicacao'], errors='coerce', utc=True)
        auto_related = auto_related.sort_values('_data', ascending=False, kind='stable')
        for _, art in auto_related.head(60).iterrows():
            title = html.escape(str(art.get('titulo','')))
            vehicle = html.escape(str(art.get('veiculo','')))
            date = html.escape(str(art.get('data_publicacao','')))
            if valid_url(art.get('url','')):
                st.markdown(f'**{title}**  \n{vehicle} · {date} · [Ler reportagem]({art["url"]})')
            else:
                st.write(title, vehicle, date)
    st.divider()
    if sub.empty:
        st.info('Nenhuma indicação cadastrada/verificada para este órgão.')
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
st.caption('Catálogo editorial, sujeito a revisão. Notícias coletadas não são nomeações confirmadas. Atualização automática executada por workflow separado.')
