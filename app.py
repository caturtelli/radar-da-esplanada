"""Radar 2.0: apresentação sobre histórico e curadoria preservados."""
import json
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import replace
from navigation import Route, decode_route, route_params
import pandas as pd
import streamlit as st
# Cloud sessions may retain imported modules across a repository update.
# Reload the analysis modules once when their deployed engine version changes.
import importlib
import identificar_nomes as name_engine
import classificar_noticias as organ_engine
import radar_model as radar_engine
if getattr(name_engine, 'ENGINE_VERSION', None) != '2.1.3':
    importlib.reload(organ_engine)
    importlib.reload(name_engine)
    importlib.reload(radar_engine)
from radar_model import read_csv, build_index, filter_rows, is_recent, STATUSES
from identificar_nomes import norm

st.set_page_config(page_title='Radar da Esplanada', page_icon='🏛️', layout='wide')
BASE = Path(__file__).resolve().parent
st.markdown('''<style>
.stApp {background:#f4f6fa}
.block-container {max-width:1320px;padding-top:2.5rem;padding-bottom:3rem}
html,body,[class*=css] {font-family:Arial,sans-serif}
[data-testid=stSidebar] {min-width:280px;max-width:300px}
[data-testid=stMain] .stButton button {min-height:48px;text-align:left;font-size:1rem;border-color:#cad8e4}
[data-testid=stMain] .stButton button:hover {border-color:#147d92;color:#126c80;background:#edf8fa}
[data-testid=stVerticalBlockBorderWrapper] {border-radius:14px}
[data-testid=stMetricLabel] {font-size:.9rem}
.stCaption {color:#536778}
[data-testid=stRadio] label {font-size:1rem}
h1,h2,h3 {color:#16334b;letter-spacing:-.025em}
[data-testid="stMetric"] {background:white;border:1px solid #dce4eb;border-radius:12px;padding:18px}
[data-testid="stSidebar"] {background:#eaf0f5}
.stButton button,.stLinkButton a {border-radius:8px}
</style>''', unsafe_allow_html=True)

st.caption('BRASÍLIA / MONITORAMENTO JORNALÍSTICO')
st.title('Radar da Esplanada')
st.write('Acompanhe os nomes e as notícias de cada ministério. Escolha um cartão para começar.')

@st.cache_data(ttl=60)
def load_data(signature, engine_version):
    curated = read_csv(BASE,'indicacoes.csv')
    sources = read_csv(BASE,'noticias.csv')
    catalog = read_csv(BASE,'catalogo_orgaos.csv')
    collected = read_csv(BASE,'noticias_coletadas.csv')
    return curated, sources, catalog, build_index(collected,curated,catalog)

files = ['indicacoes.csv','noticias.csv','catalogo_orgaos.csv','noticias_coletadas.csv']
try:
    curated, sources, catalog, rows = load_data(tuple((BASE/f).stat().st_mtime_ns if (BASE/f).exists() else 0 for f in files), name_engine.ENGINE_VERSION)
except (OSError, ValueError, AttributeError) as exc:
    st.error(f'Não foi possível carregar o radar: {exc}'); st.stop()
if catalog.empty:
    st.error('Catálogo de órgãos não encontrado.'); st.stop()

try:
    status = json.loads((BASE/'status_coleta.json').read_text())
except (OSError, ValueError):
    status = {}
when = pd.to_datetime(status.get('ultima_tentativa_utc'), errors='coerce', utc=True)
if pd.notna(when):
    st.caption('Coleta automática: '+when.tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y às %H:%M')+' · horário de Brasília')
if pd.notna(when) and pd.Timestamp.now(tz='UTC')-when > pd.Timedelta(hours=1): st.warning('A última coleta registrada tem mais de uma hora. A atualização pode estar atrasada.')
if status.get('falhas'): st.warning('A última coleta registrou falhas. Parte das fontes pode estar desatualizada.')

all_people=sorted(set(curated.get('nome', [])) | {p for r in rows for p in r['pessoas']})
org_names=catalog.orgao.tolist()
route,route_warning=decode_route(st.query_params.to_dict(),org_names,all_people)
if route_warning: st.info(route_warning)

def navigate(target):
    # One atomic change creates one browser-history entry. Reruns do not write URLs.
    params=route_params(target,org_names,all_people,st.query_params.to_dict())
    if params!=st.query_params.to_dict(): st.query_params.from_dict(params)

def change_view():
    navigate(Route(view=st.session_state.radar_view))

def change_person():
    navigate(Route(view='Pessoas',person=st.session_state.person_choice,category=route.category))

def change_category():
    navigate(Route(category=st.session_state.org_category))

# Read URL on every run, including browser Back/Forward and shared deep links.
# Updating widget state before construction also clears stale details from the prior route.
st.session_state.radar_view=route.view
st.session_state.selected_org=route.org
view=st.radio('Navegar pelo Radar',['Ministérios e órgãos','Pessoas','Últimas movimentações','Todas as notícias','Cadastro editorial'],horizontal=True,label_visibility='collapsed',key='radar_view',on_change=change_view)
with st.sidebar:
    st.header('Buscar e filtrar')
    query = st.text_input('Buscar pessoa, órgão ou notícia', placeholder='Nome, sobrenome ou palavra-chave')
    organs = st.multiselect('Filtrar órgãos', sorted(catalog.orgao.tolist()),placeholder='Todos os órgãos')
    states = st.multiselect('Natureza da informação', STATUSES,placeholder='Todas as situações')
    vehicles = st.multiselect('Veículos', sorted({r.get('veiculo','') for r in rows} - {''}),placeholder='Todos os veículos')
    recent = st.checkbox('Publicadas nas últimas 24 horas')
    period = st.radio('Período',['Desde o segundo turno','Todo o histórico'])
    st.caption('Filtros combinados. A data de publicação define a janela de 24 horas; a captura não transforma uma notícia antiga em novidade.')
    st.caption('Classificação por manchetes. Nomeação noticiada exige checagem oficial. Menções não contam como indicações.')
filtered = filter_rows(rows,query,organs,states,vehicles,recent)
if period=='Desde o segundo turno':
    from radar_model import since_second_round
    filtered = [r for r in filtered if since_second_round(r)]
people = sorted(set(curated.get('nome', [])) | {p for r in rows for p in r['pessoas']})
a,b,c,d=st.columns(4)
a.metric('Órgãos no catálogo',len(catalog))
b.metric('Pessoas identificadas',len(people))
c.metric('Notícias no histórico',len(rows))
d.metric('Publicadas em 24h',sum(is_recent(r) for r in rows))
st.divider()
coverage_path=BASE/'cobertura_historica.json'
if coverage_path.exists():
    try:
        coverage=json.loads(coverage_path.read_text())
        stamp=pd.to_datetime(coverage.get('executado_em'),errors='coerce',utc=True)
        stamp_text=stamp.tz_convert('America/Sao_Paulo').strftime('%d/%m às %H:%M') if pd.notna(stamp) else 'data não informada'
        st.caption(f'Histórico ampliado em {stamp_text}: {coverage.get("orgaos_consultados",0)} órgãos consultados · período {coverage.get("inicio","")} a {coverage.get("fim","")} · {coverage.get("novas",0)} reportagens acrescentadas. Cobertura sujeita a lacunas do RSS.')
    except (OSError,ValueError): pass

def valid_url(url):
    try:
        p=urlparse(str(url)); return p.scheme in ('http','https') and bool(p.netloc)
    except ValueError: return False

def article(row, person=None):
    with st.container(border=True):
        title=str(row.get('titulo','Sem título'))
        vehicle=str(row.get('veiculo',''))
        while vehicle and title.endswith(' - '+vehicle): title=title[:-len(' - '+vehicle)]
        st.markdown('**'+title+'**')
        state = row.get('estados',{}).get(person,row.get('situacao','Registro editorial'))
        date=pd.to_datetime(row.get('data_publicacao',''),errors='coerce',utc=True)
        published=date.tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y · %H:%M') if pd.notna(date) else 'Data não informada'
        st.caption(' · '.join(str(x) for x in [row.get('veiculo',''),published,state] if x))
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
    st.session_state[key]=min(route.page,pages)
    def change_page(): navigate(replace(route,page=int(st.session_state[key])))
    page=st.number_input('Página de reportagens',min_value=1,max_value=pages,key=key,on_change=change_page)
    st.caption(f'{len(items)} reportagem(ns) · página {page} de {pages}')
    for row in items[(page-1)*20:page*20]: article(row,person)

def editorial(items):
    if items.empty: return
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
    target=route.person
    if target and target not in available:
        available=sorted(set(available)|{target})
        st.caption('A ficha foi aberta pelo endereço; os filtros atuais podem limitar suas reportagens.')
    if not available: st.info('Nenhuma pessoa encontrada.')
    else:
        st.session_state.person_choice=target if target in available else None
        person=st.selectbox('Selecionar pessoa',available,index=None,placeholder='Escolha uma pessoa',key='person_choice',on_change=change_person)
        if person is None:
            st.info('Selecione uma pessoa para abrir sua ficha e obter um link direto.')
        else:
            st.subheader(person)
            related=[r for r in filtered if person in r['pessoas']]
            st.caption(f'{len(related)} reportagem(ns) nos filtros atuais · {len({r.get("veiculo") for r in related})} veículo(s); veículos distintos não significam confirmações independentes.')
            st.markdown('#### Registros editoriais')
            editorial(curated[curated.nome==person])
            st.markdown('#### Histórico de reportagens')
            st.caption('Sequência de relatos publicados; diferenças entre manchetes são indícios para revisão, não mudanças confirmadas na situação.')
            articles(related,person,'person_news')
elif view=='Ministérios e órgãos':
    selected = st.session_state.get('selected_org')
    if selected:
        st.button('← Voltar aos ministérios',key='back_org',on_click=navigate,args=(Route(category=route.category),))
        org=selected
        st.subheader(org)
        related=[r for r in filtered if org in r['orgaos']]
        from radar_model import organ_people
        names=organ_people(related,curated,org)
        x,y=st.columns(2)
        x.metric('Pessoas identificadas',len(names))
        y.metric('Reportagens encontradas',len(related))
        if query or states or vehicles or recent or organs:
            st.caption('Esta página está usando os filtros da barra lateral.')
        if names:
            st.markdown('### Pessoas e movimentações')
            st.caption('Cada nome reúne as fontes associadas a este órgão. Menção isolada não equivale a indicação.')
            for person,items in names.items():
                with st.container(border=True):
                    st.markdown('#### '+person)
                    situations=sorted({r['estados'].get(person,'Menção') for r in items})
                    st.caption(' · '.join(situations) if situations else 'Registro editorial')
                    st.button('Abrir ficha de '+person,key='org_person_'+person,on_click=navigate,args=(Route(view='Pessoas',person=person,category=route.category),))
                    if items:
                        latest=items[0]
                        st.write(latest.get('titulo',''))
                        if valid_url(latest.get('url','')): st.link_button('Ler fonte mais recente ↗',latest['url'])
            editorial(curated[curated.ministerio==org])
        else:
            st.info('Ainda não há nomes associados com segurança neste recorte. Consulte as reportagens abaixo ou amplie os filtros.')
        st.markdown('### Todas as reportagens deste órgão')
        articles(related,key='org_news_'+org)
    else:
        st.subheader('Escolha um ministério ou órgão')
        st.caption('Clique no nome do cartão para ver pessoas, movimentações e fontes.')
        st.session_state.org_category=route.category
        category=st.radio('Mostrar',['Ministérios','Órgãos centrais','Entidades','Todos os 79 órgãos'],horizontal=True,key='org_category',on_change=change_category)
        choices=catalog.copy()
        if category=='Ministérios': choices=choices[choices.categoria=='Ministério']
        elif category=='Órgãos centrais': choices=choices[choices.categoria=='Presidência e órgãos centrais']
        elif category=='Entidades': choices=choices[choices.categoria.str.startswith('Entidades')]
        if organs: choices=choices[choices.orgao.isin(organs)]
        from radar_model import organ_people
        summaries={o:organ_people([r for r in filtered if o in r['orgaos']],curated,o) for o in choices.orgao}
        if query:
            choices=choices[choices.orgao.map(lambda o: norm(query) in norm(o) or any(norm(query) in norm(p) for p in summaries[o]) or any(o in r['orgaos'] for r in filtered))]
        if choices.empty: st.info('Nenhum órgão encontrado com estes filtros.')
        for start in range(0,len(choices),3):
            cols=st.columns(3)
            for col,record in zip(cols,choices.iloc[start:start+3].to_dict('records')):
                org=record['orgao']
                related=[r for r in filtered if org in r['orgaos']]
                names=summaries[org]
                label=org.replace('Ministério da ','').replace('Ministério das ','').replace('Ministério do ','').replace('Ministério dos ','').replace('Ministério de ','')
                with col.container(border=True):
                    st.button(label+' →',key='open_org_'+org,use_container_width=True,on_click=navigate,args=(Route(org=org,category=route.category),))
                    st.caption(f'{len(names)} pessoa(s) · {len(related)} reportagem(ns)')
                    if names: st.write(' · '.join(list(names)[:3])+(' …' if len(names)>3 else ''))
                    else: st.caption('Nenhum nome identificado neste recorte')
                    if related and any(is_recent(r) for r in related): st.badge('Notícias em 24h',color='green')
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
st.caption('Cobertura por RSS: pode haver lacunas. Sem notícia encontrada não significa ausência de negociação.')
st.caption('Triagem automática revisável · fontes originais preservadas · sem pontuação automática de credibilidade ou probabilidade de nomeação.')

