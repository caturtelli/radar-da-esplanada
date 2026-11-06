"""Visão derivada: nunca grava nem substitui o histórico ou a curadoria."""
from pathlib import Path
from functools import lru_cache
import pandas as pd
from classificar_noticias import associate
from identificar_nomes import registry, find_people, status_from_title, person_context

STATUSES = ['Especulação', 'Negociação', 'Convite noticiado', 'Negativa', 'Nomeação noticiada', 'Menção']
ENGINE_VERSION = '2.2.0'

def read_csv(base, name):
    path = Path(base) / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, encoding='utf-8-sig').fillna('')
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

def build_index(collected, curated, catalog):
    rows = collected.to_dict('records')
    names = registry([r.get('titulo','') for r in rows], curated.get('nome', []))
    orgs = catalog.orgao.tolist()
    result = []
    seen = set()
    for row in rows:
        key = row.get('url') or (row.get('titulo'), row.get('data_publicacao'))
        if key in seen:
            continue
        seen.add(key)
        title = row.get('titulo','')
        people = find_people(title, names)
        associations = associate(title, orgs)
        # Evidence is scoped to each person: no cross product of names and ministries.
        links = {}
        states = {}
        for person in people:
            context = person_context(title, person, names)
            links[person] = associate(context, orgs) if context else []
            states[person] = status_from_title(title, person, names)
        result.append(dict(row, pessoas=people, orgaos=associations,
                           vinculos=links, estados=states,
                           situacao=status_from_title(title) if not people else ' / '.join(sorted(set(states.values())))))
    from collections import Counter
    import hashlib
    from identificar_nomes import norm
    titles = Counter(norm(r.get('titulo','')).split(' - ')[0] for r in result)
    for row in result:
        title_key = norm(row.get('titulo','')).split(' - ')[0]
        row['article_id'] = hashlib.sha256(str(row.get('url') or title_key).encode()).hexdigest()[:24]
        row['grupo_republicacao'] = hashlib.sha256(title_key.encode()).hexdigest()[:16] if titles[title_key] > 1 else ''
    return result

@lru_cache(maxsize=20000)
def timestamp(value):
    return pd.to_datetime(value, errors='coerce', utc=True)

def is_recent(row, now=None):
    now = now if now is not None else pd.Timestamp.now(tz='UTC')
    date = timestamp(row.get('data_publicacao',''))
    return bool(pd.notna(date) and now - pd.Timedelta(hours=24) <= date <= now)

def filter_rows(rows, query='', organs=(), statuses=(), vehicles=(), recent=False, now=None):
    from identificar_nomes import norm
    output = []
    for row in rows:
        text = ' '.join([row.get('titulo',''), row.get('veiculo',''), *row['pessoas'], *row['orgaos']])
        if query and norm(query) not in norm(text): continue
        if organs and not set(organs).intersection(row['orgaos']): continue
        values = set(row['estados'].values()) or {row['situacao']}
        if statuses and not set(statuses).intersection(values): continue
        if vehicles and row.get('veiculo','') not in vehicles: continue
        if recent and not is_recent(row, now): continue
        output.append(row)
    return sorted(output, key=lambda r: str(timestamp(r.get('data_publicacao',''))) if pd.notna(timestamp(r.get('data_publicacao',''))) else '', reverse=True)


SECOND_ROUND = pd.Timestamp('2026-10-25T17:00:00', tz='America/Sao_Paulo').tz_convert('UTC')

def since_second_round(row):
    value=timestamp(row.get('data_publicacao',''))
    return bool(pd.notna(value) and value >= SECOND_ROUND)

def organ_people(rows, curated, org):
    """Somente vínculos explícitos por trecho e registros editoriais deste órgão."""
    from collections import defaultdict
    grouped=defaultdict(list)
    for row in rows:
        for person,orgs in row.get('vinculos',{}).items():
            if org in orgs and row.get('estados',{}).get(person,'Menção')!='Menção': grouped[person].append(row)
    if not curated.empty:
        for person in curated.loc[curated.ministerio==org,'nome']:
            grouped.setdefault(person,[])
    return dict(sorted(grouped.items(),key=lambda x:(-len(x[1]),x[0])))


def minister_targets(row, person, catalog, registered):
    """Exige destino ministerial no trecho da pessoa; exclui segundo escalão e tribunais."""
    import re
    from identificar_nomes import norm
    context = norm(person_context(row.get('titulo', '').split(' - ')[0], person, registered))
    if not context:
        return []
    # A current minister mentioning someone or leaving office is not a candidate.
    if re.search(r'\b(?:deixar|deixe|sair|saia|demissao|exoneracao|demitid[oa])\b', context):
        return []
    subordinate = r'(?:secretari[oa](?:-executiv[oa])?|secretaria(?:-executiva)?|diretor(?:ia)?|presidente|presidencia|conselh[oa]|assessor|chefe de gabinete)'
    if re.search(r'\b(?:para|assumir|comandar|chefiar)\s+(?:(?:a|o|ser|uma?|novo|nova)\s+)*' + subordinate + r'\b', context):
        return []
    if re.search(r'\b(?:stf|stj|tse|tst|stm|tribunal|supremo)\b', context):
        return []
    # Locate the candidate as subject, rather than e.g. "reeleição de X pode levar alguém".
    aliases = [person, person.split()[0], person.split()[-1]]
    from identificar_nomes import find_people
    subject = False
    predicate = r'\b(?:cotad[oa]s?|sondad[oa]s?|favorit[oa]s?|negocia|negociacao|convite|convidad[oa]s?|convidou|assumir|assumira|comandar|ganha forca|nome para|indicad[oa]|nega|negou|descarta|descartou|recusa|recusou|rejeita|rejeitou|nomead[oa]|nomeou|(?:pode|deve|podera)\s+(?:voltar a |continuar a )?ser ministr[oa])\b'
    for alias in aliases:
        if find_people(alias, registered) != [person]:
            continue
        for match in re.finditer(r'(?<!\w)' + re.escape(norm(alias)) + r'(?!\w)', context):
            before = context[:match.start()]
            after = context[match.end():]
            if re.search(r'\b(?:reeleicao|sucessao|derrota|vitoria|filh[oa]|esposa|marido)\s+(?:d[eo]\s+)?$', before):
                continue
            match_predicate = re.search(predicate, after[:110])
            if match_predicate and not re.search(r'\b(?:nomes|outros|outras|pessoas)\b', after[:match_predicate.start()]):
                subject = True
    if not subject:
        return []
    ministries = set(catalog.loc[catalog.categoria == 'Ministério', 'orgao'])
    # Central organs are included only with an explicit ministerial office in the title.
    explicit = bool(re.search(r'\b(?:para|como|ser|sera|assumir|cotad[oa]s? a)\s+(?:(?:o|a|novo|nova|proximo|proxima)\s+)*ministr[oa](?:-chefe)?\b', context))
    links = row.get('vinculos', {}).get(person, [])
    if explicit:
        links = associate(context + ' cotado', catalog.orgao.tolist())
    destinations = [org for org in links if org in ministries or (explicit and org in set(catalog.loc[catalog.categoria == 'Presidência e órgãos centrais', 'orgao']))]
    # "Ministro X pode comentar..." does not qualify merely by naming a ministry.
    movement = bool(re.search(predicate, context))
    if not (explicit or movement):
        return []
    return destinations or (['Pasta não informada'] if explicit else [])


def minister_candidates(rows, catalog, now=None):
    """Último relato por pessoa/pasta, sem converter cotação em confirmação."""
    now = now if now is not None else pd.Timestamp.now(tz='UTC')
    registered = registry([r.get('titulo', '') for r in rows], [p for r in rows for p in r.get('pessoas', [])])
    events = {}
    for row in rows:
        date = timestamp(row.get('data_publicacao', ''))
        if pd.isna(date) or date > now:
            continue
        for person in row.get('pessoas', []):
            state = row.get('estados', {}).get(person, 'Menção')
            if state == 'Menção':
                continue
            for org in minister_targets(row, person, catalog, registered):
                events.setdefault((person, org), []).append((date, state, row))
    candidates = []
    active = {'Especulação', 'Negociação', 'Convite noticiado'}
    for (person, org), news in events.items():
        news.sort(key=lambda e: e[0], reverse=True)
        latest = news[0][0]
        latest_events = [e for e in news if e[0] == latest]
        # Conflicting simultaneous headlines and later generic denials suppress the highlight.
        if any(e[1] not in active for e in latest_events):
            continue
        generic = events.get((person, 'Pasta não informada'), []) if org != 'Pasta não informada' else []
        if any(d >= latest and s not in active for d, s, r in generic):
            continue
        candidates.append({'nome': person, 'orgao': org, 'situacao': news[0][1],
                           'fonte': news[0][2], 'reportagens': [e[2] for e in news]})
    named = {c['nome'] for c in candidates if c['orgao'] != 'Pasta não informada'}
    candidates = [c for c in candidates if c['orgao'] != 'Pasta não informada' or c['nome'] not in named]
    return sorted(candidates, key=lambda c: (timestamp(c['fonte'].get('data_publicacao')), c['nome']), reverse=True)

