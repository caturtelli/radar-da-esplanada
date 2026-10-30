"""Identificação conservadora em manchetes, sem inferir identidade ambígua."""
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache

SEEDS = ['Rafael Fonteles', 'Camilo Santana', 'Simone Tebet', 'Wagner Moura',
         'Margareth Menezes', 'Pierpaolo Bottini', 'Luiz Marinho', 'André Janones',
         'João Campos', 'Fátima Bezerra', 'Lincoln Gakiya', 'Fernando Haddad',
         'Renan Filho', 'Geraldo Alckmin', 'Rui Costa', 'Paulo Paim',
         'Rodrigo Pacheco', 'Gleisi Hoffmann', 'Márcio Tavares']
NAME = re.compile(r'\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+(?:\s+(?:(?:de|da|do|dos|das)\s+)?[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+){1,4}\b')
BLOCK = {'ministerio','secretaria','banco','governo','federal','republica','civil',
         'brasil','supremo','tribunal','publica','congresso','camara','senado',
         'folha','globo','estado','news','justica','seguranca',
         'para','sobre','apos','com','sem','novo','nova','nesta','neste',
         'portal','ministerios','presidencia','aeroportos','portos'}

@lru_cache(maxsize=20000)
def norm(t):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(t or '').casefold()) if not unicodedata.combining(c))

def contains(text, phrase):
    return bool(re.search(r'(?<!\w)' + re.escape(norm(phrase)) + r'(?!\w)', norm(text)))

def discover(title):
    title = re.sub(r'\b(?:Senador[a]?|Deputad[oa]|Ministr[oa]|Governador[a]?|Presidente)\s+', '', str(title))
    return [m.group() for m in NAME.finditer(title.split(' - ')[0])
            if not set(norm(m.group()).split()) & BLOCK]

def registry(titles, registered=()):
    # Full forms across the entire corpus are resolved before single surnames.
    names = list(SEEDS) + list(registered)
    for title in titles:
        names.extend(discover(title))
    unique = {norm(n): n for n in names if len(str(n).split()) >= 2}
    # A shorter full form is an alias only when it has exactly one longer match.
    for key in list(unique):
        longer = [k for k in unique if k != key and k.startswith(key + ' ')]
        if len(longer) == 1:
            del unique[key]
    return sorted(unique.values())

def find_people(title, registered=()):
    title = str(title).split(' - ')[0]
    names = registry([], registered)
    aliases = defaultdict(set)
    for name in names:
        parts = name.split()
        for alias in [name, parts[0], parts[-1], ' '.join(parts[:2])]:
            if len(norm(alias)) >= 4 and norm(alias) not in BLOCK:
                aliases[norm(alias)].add(name)
    found = set()
    for alias, candidates in aliases.items():
        if len(candidates) == 1 and contains(title, alias):
            found.update(candidates)
    return sorted(found)

def person_context(title, person, registered=()):
    # Split contrast/coordination to avoid transferring another person's denial.
    chunks = re.split(r'[;.!?]|\s+(?:mas|enquanto)\s+', str(title), flags=re.I)
    matching = [c for c in chunks if find_people(c, registered) == [person]]
    return ' '.join(matching) if len(matching) == 1 else ''

def status_from_title(title, person=None, registered=()):
    t = norm(person_context(title, person, registered) if person else title)
    if not t:
        return 'Menção'
    if re.search(r'\b(nao foi nomead[oa]|nao sera|nao recebeu|nao houve|nega|negou|descarta|descartou|recusa|recusou|desmente)\b', t):
        return 'Negativa'
    if re.search(r'\b(pode|deve|podera|seria|cotad[oa]|especula|favorit[oa]|sondad[oa]|disputa)\b', t):
        return 'Especulação'
    if re.search(r'\b(foi nomead[oa]|nomeou|nomeacao confirmada|anunciou a nomeacao)\b', t):
        return 'Nomeação noticiada'
    if re.search(r'\b(convite|convidad[oa]|convidou)\b', t):
        return 'Convite noticiado'
    if re.search(r'\b(negocia|negociacao|conversa|tratativas)\b', t):
        return 'Negociação'
    if re.search(r'\b(indicad[oa]|indica|assumira|ganha forca|nome para|comandar)\b', t):
        return 'Especulação'
    return 'Menção'

def group_news(rows, registered=()):
    known = registry([r.get('titulo','') for r in rows], registered)
    groups, unmatched = defaultdict(list), []
    for row in rows:
        names = find_people(row.get('titulo',''), known)
        if not names:
            unmatched.append(row)
        for name in names:
            groups[name].append(row)
    return dict(groups), unmatched
