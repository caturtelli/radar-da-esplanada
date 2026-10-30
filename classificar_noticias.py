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
    """Todos os órgãos participam; vínculo administrativo não transfere indicação."""
    t = norm(title)
    found = []
    # A hypothetical new Security ministry must not be folded into Justice.
    hypothetical_security = ('ministerio da seguranca' in t or 'ministerio de seguranca' in t) and 'ministerio da justica' not in t

    for org in sorted(set(catalog_names)):
        if hypothetical_security and org == 'Ministério da Justiça e Segurança Pública':
            continue
        official = norm(org)
        patterns = [r'(?<!\w)' + re.escape(official) + r'(?!\w)']
        if official.startswith('ministerio '):
            short = re.sub(r'^ministerio (?:da |das |do |dos |de )?', '', official)
            if len(short.split()) > 1:
                patterns.append(r'(?<!\w)' + re.escape(short) + r'(?!\w)')
            elif MOVEMENT.search(t):
                patterns.append(r'(?:para|na|a|da|do)\s+(?:a |o |chefiar |comandar |assumir |ministr[oa] d[ao] )?'+re.escape(short)+r'(?!\w)')
        # Curtos e siglas exigem grafia exata; evita ANS dentro de palavras.
        if len(org) <= 6 and org.isupper():
            matched = bool(re.search(r'(?<!\w)' + re.escape(org) + r'(?!\w)', str(title)))
        else:
            matched = any(re.search(p, t) for p in patterns)
        # Aliases editoriais com palavras genéricas só em contexto de movimentação.
        if not matched and MOVEMENT.search(t):
            matched = any(re.search(p,t) for p in ALIASES.get(org, []))
            if matched and org in {'Ministério da Defesa','Ministério da Saúde','Ministério da Cultura','Ministério da Fazenda'}:
                short={'Ministério da Defesa':'defesa','Ministério da Saúde':'saude','Ministério da Cultura':'cultura','Ministério da Fazenda':'fazenda'}[org]
                matched=bool(re.search(r'(?:para|na|a|da|do)\s+(?:a |o |chefiar |comandar |assumir |ministr[oa] d[ao] )?'+short+r'\b',t))
        if matched:
            found.append(org)
    return found
