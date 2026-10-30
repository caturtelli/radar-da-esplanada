"""Rotas do Radar: a URL é a fonte de verdade da navegação.

Usa query params nativos, sem scripts injetados ou dependências de domínio.
Filtros jornalísticos permanecem na sessão; rotas podem ser compartilhadas.
"""
from dataclasses import dataclass
import hashlib
import re
import unicodedata

VIEWS = {
    'ministerios': 'Ministérios e órgãos',
    'pessoas': 'Pessoas',
    'movimentacoes': 'Últimas movimentações',
    'noticias': 'Todas as notícias',
    'cadastro': 'Cadastro editorial',
}
CATEGORIES = {
    'ministerios': 'Ministérios', 'centrais': 'Órgãos centrais',
    'entidades': 'Entidades', 'todos': 'Todos os 79 órgãos',
}
ROUTE_KEYS = {'tela', 'orgao', 'pessoa', 'pagina', 'categoria'}

@dataclass(frozen=True)
class Route:
    view: str = 'Ministérios e órgãos'
    org: str | None = None
    person: str | None = None
    page: int = 1
    category: str = 'Ministérios'


def slug(text):
    text=unicodedata.normalize('NFKD',str(text)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','-',text).strip('-')


def slug_map(names, organs=False):
    result={}
    for name in sorted(set(names)):
        short=re.sub(r'^Ministério (?:da |das |do |dos |de )?', '',name) if organs else name
        key=slug(short)
        if not key: key=hashlib.sha256(name.encode()).hexdigest()[:10]
        if key in result:
            # Both colliding names get deterministic suffixes, independent of input order.
            previous=result.pop(key)
            for value in [previous,name]:
                result[key+'-'+hashlib.sha256(value.encode()).hexdigest()[:8]]=value
        elif any(k.startswith(key+'-') and v!=name and slug(re.sub(r'^Ministério (?:da |das |do |dos |de )?', '',v) if organs else v)==key for k,v in result.items()):
            result[key+'-'+hashlib.sha256(name.encode()).hexdigest()[:8]]=name
        else:
            result[key]=name
    return result


def decode_route(params, orgs, people):
    def get(key,default=''):
        value=params.get(key,default)
        return str(value[-1] if isinstance(value,(list,tuple)) and value else value)
    view=VIEWS.get(get('tela'),'Ministérios e órgãos')
    category=CATEGORIES.get(get('categoria'),'Ministérios')
    try: page=max(1,int(get('pagina','1')))
    except (TypeError,ValueError): page=1
    if get('pessoa'):
        person=slug_map(people).get(get('pessoa'))
        if person is None: return Route(view='Pessoas'), 'A pessoa deste endereço não foi encontrada. Selecione um nome na lista.'
        return Route(view='Pessoas',person=person,page=page,category=category), ''
    if get('orgao'):
        org=slug_map(orgs,organs=True).get(get('orgao'))
        if org is None: return Route(), 'O órgão deste endereço não foi encontrado. Escolha um cartão abaixo.'
        return Route(org=org,page=page,category=category), ''
    return Route(view=view,page=page,category=category), ''


def route_params(route, orgs, people, existing=None):
    params={k:v for k,v in (existing or {}).items() if k not in ROUTE_KEYS and k not in {'embed','embed_options'}}
    if route.person:
        person_keys={v:k for k,v in slug_map(people).items()}
        if route.person not in person_keys: raise ValueError('Pessoa não cadastrada')
        params['pessoa']=person_keys[route.person]
    elif route.org:
        org_keys={v:k for k,v in slug_map(orgs,organs=True).items()}
        if route.org not in org_keys: raise ValueError('Órgão não cadastrado')
        params['orgao']=org_keys[route.org]
    elif route.view != 'Ministérios e órgãos':
        view_keys={v:k for k,v in VIEWS.items()}
        params['tela']=view_keys[route.view]
    if route.page>1: params['pagina']=str(route.page)
    if route.category!='Ministérios':
        params['categoria']={v:k for k,v in CATEGORIES.items()}[route.category]
    return params
