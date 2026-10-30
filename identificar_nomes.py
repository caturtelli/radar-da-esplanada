"""Triagem de nomes em manchetes; nunca confirma nomeação ou convite.
Não lê conteúdo integral das reportagens. Revise todas as associações.
"""
import re
import unicodedata
from collections import defaultdict

# Nomes completos efetivamente observados nas manchetes da amostra inicial.
# Pode-se ampliar esta lista após revisão editorial; não se inferem identidades por sobrenome.
SEEDS = [
    "Rafael Fonteles", "Camilo Santana", "Simone Tebet", "Wagner Moura",
    "Margareth Menezes", "Pierpaolo Bottini", "Luiz Marinho",
    "André Janones", "João Campos", "Fátima Bezerra",
    "Lincoln Gakiya", "Fernando Haddad", "Renan Filho",
    "Geraldo Alckmin", "Rui Costa", "Paulo Paim",
    "Rodrigo Pacheco", "Gleisi Hoffmann", "Márcio Tavares",
]
EXCLUDE = {
    "lula", "luiz inacio lula da silva", "flavio bolsonaro", "jair bolsonaro",
    "governo lula", "ministerio da fazenda", "ministerio da cultura",
    "ministerio da justica", "casa civil", "stf", "supremo tribunal federal",
}
MOVES = re.compile(
    r"\b(cotad[oa]s?|nomead[oa]s?|nomeac(?:ao|oes)|indicad[oa]s?|"
    r"indicac(?:ao|oes)|assumir|assumira|comandar|chefia|"
    r"convite|convidad[oa]s?|ganha forca|favorit[oa]s?|"
    r"escolh|novo ministro|nova ministra|pode ser ministro|"
    r"para (?:a |o )?(?:fazenda|cultura|justica|casa civil|defesa|itamaraty)|"
    r"ministerio|chanceler)\b", re.I
)
NEGATION = re.compile(
    r"\b(nega|negou|nega ter|descarta|descartou|recusa|recusou|"
    r"nao recebeu|nao houve|nao tratou|desmente|desmentiu)\b", re.I
)
# Suficientemente restrito para não captar nomes de veículos.
NAME = re.compile(
    r"(?<![\w])([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+"
    r"(?:\s+(?:de|da|do|dos|das))?"
    r"\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+"
    r"(?:\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)?)"
)

def norm(t):
    t = unicodedata.normalize('NFKD',str(t or '').casefold())
    return ''.join(c for c in t if not unicodedata.combining(c))

def status_from_title(title):
    t = norm(title)
    if NEGATION.search(t):
        return "Há negativa na manchete"
    if re.search(r"\b(foi nomead[oa]|nomeacao confirmada|nomeou|anunciou a nomeacao)\b",t):
        return "Manchete relata nomeação — verificar fonte oficial"
    return "Menção em contexto de possível indicação — não verificada"

def find_people(title, registered=()):
    t = str(title or '').split(' - ')[0]
    nt = norm(t)
    if not MOVES.search(nt):
        return []
    names = set()
    for name in list(SEEDS) + list(registered):
        if len(name.split()) < 2:
            continue
        if re.search(r'(?<!\w)' + re.escape(norm(name)) + r'(?!\w)', nt):
            names.add(name)
    # Extração conservadora de novos nomes: apenas em construções fortes.
    patterns = [
        r"(?:nome de|cotad[oa]\s+para|convidar|indicar)\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wáàâãéêíóôõúç]+\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][\wáàâãéêíóôõúç]+)",
        r"([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+)\s+(?:e\s+|é\s+|entra\s+|pode\s+|ganha\s+|surge\s+|deve\s+|nega\s+|negou\s+|aceitaria\s+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern,t):
            candidate=match.group(1).strip()
            if norm(candidate) not in EXCLUDE and len(candidate.split())==2:
                names.add(candidate)
    return sorted(names)

def group_news(rows, registered=()):
    groups=defaultdict(list)
    unmatched=[]
    for row in rows:
        names=find_people(row.get('titulo',''),registered)
        if not names:
            unmatched.append(row)
        for name in names:
            groups[name].append(row)
    return dict(groups), unmatched
