"""Radar 2.0: apresentação sobre histórico e curadoria preservados."""
import json
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st
from radar_model import read_csv, build_index, filter_rows, is_recent, STATUSES
from identificar_nomes import norm

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
BASE = Path(__file__).resolve().parent
st.markdown('''<style>
.stApp {background:#f4f6fa}
.block-container {max-width:1440px;padding-top:2rem}
h1,h2,h3 {color:#16334b;letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;border:1px solid #dce4eb;border-radius:12px;padding:18px}
[data-testid="stSidebar"] {background:#eaf0f5}
.stButton button,.stLinkButton a {border-radius:8px}
</style>''', unsafe_allow_html=True)

@st.cache_data(ttl=60)
def load_data(signature):
    curated = read_csv(BASE,'indicacoes.csv')
    sources = read_csv(BASE,'noticias.csv')
    catalog = read_csv(BASE,'catalogo_orgaos.csv')
    collected = read_csv(BASE,'noticias_coletadas.csv')
    return curated, sources, catalog, build_index(collected,curated,catalog)

files = ['indicacoes.csv','noticias.csv','catalogo_orgaos.csv','noticias_coletadas.csv']
try:
    curated, sources, catalog, rows = load_data(tuple((BASE/f).stat().st_mtime_ns if (BASE/f).exists() else 0 for f in files))
except (OSError, ValueError, AttributeError) as exc:
    st.error(f'Não foi possível carregar o radar: {exc}'); st.stop()
if catalog.empty:
    st.error('Catálogo de órgãos não encontrado.'); st.stop()

st.caption('BRASÍLIA / MONITORAMENTO JORNALÍSTICO')
st.title('Radar da Esplanada')
st.write('Pessoas, negociações e fontes para acompanhar a formação do governo.')
try:
    status = json.loads((BASE/'status_coleta.json').read_text())
except (OSError, ValueError):
    status = {}
when = pd.to_datetime(status.get('ultima_tentativa_utc'), errors='coerce', utc=True)
if pd.notna(when):
    st.caption('Última tentativa de coleta: '+when.tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y às %H:%M')+' · horário de Brasília')
if status.get('falhas'): st.warning('A última coleta registrou falhas. Parte das fontes pode estar desatualizada.')

with st.sidebar:
    st.header('Explorar o radar')
    view = st.radio('Visualização',['Ministérios e órgãos','Últimas movimentações','Pessoas','Todas as notícias','Cadastro editorial'])
    query = st.text_input('Buscar pessoa, órgão ou notícia', placeholder='Nome, sobrenome ou palavra-chave')
    organs = st.multiselect('Órgãos', sorted(catalog.orgao.tolist()))
    states = st.multiselect('Natureza da informação', STATUSES)
    vehicles = st.multiselect('Veículos', sorted({r.get('veiculo','') for r in rows} - {''}))
    recent = st.checkbox('Publicadas nas últimas 24 horas')
    st.caption('Filtros combinados. A data de publicação define a janela de 24 horas; a captura não transforma uma notícia antiga em novidade.')
    st.caption('Classificação por manchetes. Nomeação noticiada exige checagem oficial. Menções não contam como indicações.')
filtered = filter_rows(rows,query,organs,states,vehicles,recent)
people = sorted(set(curated.get('nome', [])) | {p for r in rows for p in r['pessoas']})
a,b,c,d=st.columns(4)
a.metric('Órgãos no catálogo',len(catalog))
b.metric('Pessoas identificadas',len(people))
c.metric('Notícias no histórico',len(rows))
d.metric('Publicadas em 24h',sum(is_recent(r) for r in rows))
st.divider()

def valid_url(url):
    try:
        p=urlparse(str(url)); return p.scheme in ('http','https') and bool(p.netloc)
    except ValueError: return False

def article(row, person=None):
    with st.container(border=True):
        st.markdown('**'+str(row.get('titulo','Sem título'))+'**')
        state = row.get('estados',{}).get(person,row.get('situacao','Registro editorial'))
        st.caption(' · '.join(str(x) for x in [row.get('veiculo',''),row.get('data_publicacao',''),state] if x))
        if is_recent(row): st.badge('Últimas 24 horas')
        if row.get('grupo_republicacao'): st.caption('Possível republicação: manchete idêntica em outros registros. Independência não verificada.')
        if row.get('orgaos'): st.caption('Órgãos mencionados: '+ ' · '.join(row['orgaos']))
        if row.get('jornalista'): st.caption('Jornalista: '+row['jornalista'])
        for field in ['tipo_evidencia','observacao']:
            if row.get(field): st.write(row[field])
        if valid_url(row.get('url','')): st.link_button('Abrir reportagem ↗',row['url'])
        else: st.caption('Link não disponível neste registro.')

def articles(items, person=None, key='news'):
    if not items: st.info('Nenhuma notícia encontrada com estes filtros.'); return
    pages=max(1,(len(items)+19)//20)
    page=st.number_input('Página de reportagens',min_value=1,max_value=pages,value=1,key=key)
    st.caption(f'{len(items)} reportagem(ns) · página {page} de {pages}')
    for row in items[(page-1)*20:page*20]: article(row,person)

def editorial(items):
    if items.empty: st.info('Sem registros editoriais para esta seleção.'); return
    st.dataframe(items[[c for c in ['nome','ministerio','cargo','situacao','tipo_movimentacao'] if c in items]],hide_index=True,use_container_width=True)
    for _,item in items.iterrows():
        with st.expander(f'{item["nome"]} · {item["cargo"]} · {item["situacao"]}'):
            for field,label in [('escalao','Escalão'),('tipo_movimentacao','Movimentação'),('evidencia_favoravel','Evidências favoráveis'),('evidencia_contraria','Evidências contrárias'),('autor_verificado','Autor verificado')]:
                if item.get(field): st.write(f'**{label}:** {item[field]}')
            if valid_url(item.get('fonte_verificada','')): st.link_button('Fonte cadastrada ↗',item['fonte_verificada'])
            related=sources[sources.indicacao_id == item.indicacao_id] if not sources.empty else sources
            for row in related.to_dict('records'): article(row)

if view=='Últimas movimentações':
    st.subheader('Últimas movimentações')
    st.caption('Novas publicações não equivalem a novas confirmações ou mudanças efetivas de situação.')
    st.caption('Somente notícias com indícios de movimentação; simples menções ficam em Todas as notícias.')
    articles([r for r in filtered if any(s!='Menção' for s in r['estados'].values()) or (not r['pessoas'] and r['situacao']!='Menção')])
elif view=='Todas as notícias':
    st.subheader('Notícias e fontes')
    articles(filtered)
elif view=='Pessoas':
    available=sorted({p for r in filtered for p in r['pessoas']} | {p for p in curated.get('nome',[]) if not query or norm(query) in norm(p)})
    if not available: st.info('Nenhuma pessoa encontrada.')
    else:
        person=st.selectbox('Selecionar pessoa',available)
        st.subheader(person)
        related=[r for r in filtered if person in r['pessoas']]
        st.caption(f'{len(related)} reportagem(ns) nos filtros atuais · {len({r.get("veiculo") for r in related})} veículo(s); veículos distintos não significam confirmações independentes.')
        st.markdown('#### Registros editoriais')
        editorial(curated[curated.nome==person])
        st.markdown('#### Histórico de reportagens')
        st.caption('Sequência de relatos publicados; diferenças entre manchetes são indícios para revisão, não mudanças confirmadas na situação.')
        articles(related,person,'person_news')
elif view=='Ministérios e órgãos':
    category=st.selectbox('Categoria',['Todas']+sorted(catalog.categoria.unique()))
    choices=catalog if category=='Todas' else catalog[catalog.categoria==category]
    if organs: choices=choices[choices.orgao.isin(organs)]
    if query: choices=choices[choices.orgao.map(lambda o: norm(query) in norm(o) or any(o in r['orgaos'] for r in filtered))]
    if choices.empty: st.info('Nenhum órgão encontrado.')
    else:
        st.caption(f'{len(choices)} órgãos nesta seleção · selecione um órgão para consultar suas fontes.')
        org=st.selectbox('Selecionar ministério ou órgão',choices.orgao.tolist(),key='org_selection')
        with st.expander('Visão geral dos órgãos', expanded=False):
            for start in range(0,len(choices),3):
                cols=st.columns(3)
                for col,record in zip(cols,choices.iloc[start:start+3].to_dict('records')):
                    name=record['orgao']
                    with col.container(border=True):
                        st.markdown('**'+name+'**')
                        n=sum(name in r['orgaos'] for r in filtered)
                        st.caption(f'{n} reportagem(ns) nos filtros atuais')
                        st.caption(record['categoria'])
        st.subheader(org)
        parent=choices[choices.orgao==org].iloc[0].orgao_superior
        if parent: st.caption('Vínculo de catálogo: '+parent+' · não transfere indicações entre órgãos.')
        related=[r for r in filtered if org in r['orgaos']]
        linked=sorted({p for r in related for p in r['pessoas'] if org in r['vinculos'].get(p,[])})
        st.write('**Pessoas com associação no mesmo trecho:** '+(', '.join(linked) or 'Nenhuma identificada com segurança.'))
        editorial(curated[curated.ministerio==org])
        st.markdown('#### Reportagens associadas ao órgão')
        articles(related,key='org_news')
else:
    st.subheader('Cadastro editorial')
    data=curated.copy()
    if organs: data=data[data.ministerio.isin(organs)]
    if query: data=data[data.apply(lambda r: norm(query) in norm(' '.join(r.astype(str))),axis=1)]
    levels=st.multiselect('Escalão',['Primeiro escalão / direção','Segundo escalão','A classificar'],default=['Primeiro escalão / direção','Segundo escalão','A classificar'])
    def level(cargo):
        t=norm(cargo)
        if any(s in t for s in ['secretari','diretor','superintendente']): return 'Segundo escalão'
        if any(s in t for s in ['ministr','presidente','chefe de gabinete','chefia de gabinete']): return 'Primeiro escalão / direção'
        return 'A classificar'
    data['escalao']=data.apply(lambda r:r.get('escalao','') or level(r.cargo),axis=1)
    editorial(data[data.escalao.isin(levels)])
st.divider()
st.caption('Triagem automática revisável · fontes originais preservadas · sem pontuação automática de credibilidade ou probabilidade de nomeação.')
