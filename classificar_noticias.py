"""Associação conservadora de manchetes a órgãos, sem inferir nomeações.
Somente títulos são usados; palavras da consulta de busca não são evidência.
"""
import re
import unicodedata

def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(c for c in text if not unicodedata.combining(c))

ALIASES = {
    "Ministério da Fazenda": [r"\bfazenda\b", r"\bministerio da fazenda\b"],
    "Ministério da Cultura": [r"\bcultura\b", r"\bminc\b"],
    "Ministério da Educação": [r"\beducacao\b", r"\bmec\b"],
    "Ministério da Saúde": [r"\bsaude\b"],
    "Ministério da Justiça e Segurança Pública": [r"\bjustica\b", r"\bministerio da justica\b"],
    "Ministério das Relações Exteriores": [r"\bitamaraty\b", r"\bchancelaria\b", r"\bchanceler\b", r"\brelacoes exteriores\b"],
    "Ministério das Comunicações": [r"\bcomunicacoes\b"],
    "Ministério da Agricultura e Pecuária": [r"\bagricultura\b", r"\bpecuaria\b"],
    "Ministério das Cidades": [r"\bministerio das cidades\b"],
    "Ministério da Defesa": [r"\bdefesa\b"],
    "Ministério do Meio Ambiente e Mudança do Clima": [r"\bmeio ambiente\b", r"\bministerio do clima\b"],
    "Ministério do Trabalho e Emprego": [r"\btrabalho e emprego\b", r"\bministerio do trabalho\b"],
    "Ministério dos Transportes": [r"\bministerio dos transportes\b"],
    "Ministério do Turismo": [r"\bturismo\b"],
    "Ministério de Minas e Energia": [r"\bminas e energia\b"],
    "Ministério do Planejamento e Orçamento": [r"\bplanejamento e orcamento\b", r"\bministerio do planejamento\b"],
    "Ministério da Gestão e da Inovação em Serviços Públicos": [r"\bministerio da gestao\b"],
    "Ministério do Desenvolvimento, Indústria, Comércio e Serviços": [r"\bministerio do desenvolvimento,? industria\b", r"\bmdic\b"],
    "Ministério do Desenvolvimento Agrário e Agricultura Familiar": [r"\bdesenvolvimento agrario\b"],
    "Ministério da Ciência, Tecnologia e Inovação": [r"\bciencia,? tecnologia\b"],
    "Ministério dos Direitos Humanos e Cidadania": [r"\bdireitos humanos\b"],
    "Casa Civil": [r"\bcasa civil\b"],
}
# Evitar falsas associações: menções a políticas públicas sem relação com cargos.
APPOINTMENT = re.compile(
    r"\b(minist(?:ro|ra|ros|ras|erio|erios)|pasta|esplanada|gabinete|"
    r"cotad[oa]s?|nomead[oa]s?|nomeac(?:ao|oes)|indicad[oa]s?|indicac(?:ao|oes)|"
    r"chancel(?:er|aria)|composic(?:ao|oes)|reforma ministerial|"
    r"assumir|assumira|comandar|comando|chefia|titular|convite|convidad[oa]s?|"
    r"presidencia|presidente|secretari[oa]s?|troca de ministros)\b"
)
# 'ministerio' por si só só é suficiente com indício de movimentação de cargos.
MOVEMENT = re.compile(
    r"\b(cotad[oa]s?|nomead[oa]s?|nomeac(?:ao|oes)|indicad[oa]s?|"
    r"indicac(?:ao|oes)|composic(?:ao|oes)|reforma ministerial|"
    r"assumir|assumira|comandar|chefia|titular|convite|convidad[oa]s?|"
    r"ganha forca|favorit[oa]s?|negocia|disputa|substitu|escolh|possibilidade|"
    r"novo ministro|nova ministra|proximo ministro|proxima ministra)\b"
)

def associate(title, catalog_names):
    t = norm(title)
    if not MOVEMENT.search(t):
        return []
    # Não confundir especulação sobre eventual ministério novo com pasta existente.
    if "ministerio da seguranca" in t and "ministerio da justica" not in t:
        return []
    # Referências à composição do governo derrotado não são indicações para Lula.
    if "flavio bolsonaro" in t and ("favorito" in t or "governo de flavio" in t):
        return []
    known = set(catalog_names)
    found = []
    for org, patterns in ALIASES.items():
        if org in known and any(re.search(p, t) for p in patterns):
            found.append(org)
    # Para nomes oficiais não cobertos por aliases, exigir a expressão inteira.
    for org in known:
        if org in found:
            continue
        if org.startswith("Ministério "):
            phrase = norm(org)
            if phrase in t:
                found.append(org)
    return sorted(set(found))
