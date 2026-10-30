"""Visão derivada: nunca grava nem substitui o histórico ou a curadoria."""
from pathlib import Path
import pandas as pd
from classificar_noticias import associate
from identificar_nomes import registry, find_people, status_from_title, person_context

STATUSES = ['Especulação', 'Negociação', 'Convite noticiado', 'Negativa', 'Nomeação noticiada', 'Menção']

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
