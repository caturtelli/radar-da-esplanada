"""Coleta conservadora de RSS: matérias são pistas, nunca indicações confirmadas."""
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, urlunparse, urlencode

import feedparser
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "noticias_coletadas.csv"
STATUS = BASE / "status_coleta.json"
FIELDS = ["titulo", "veiculo", "data_publicacao", "url", "busca", "nomes_mencionados", "capturado_em"]
QUERIES = [
    '"Lula" "ministério" "nome"',
    '"Lula" "ministro" "indicação"',
    '"Lula" "secretário-executivo"',
    '"governo Lula" "nomeação"',
    '"Lula" "composição do governo"',
    '"Lula" "estatais" "presidência"',
]
MAX_ROWS = 5000

def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def normalized_url(url):
    url = clean(url)
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        # Preserva links Google News para não perder URLs sem resolução confiável.
        query = [(k,v) for k,v in __import__('urllib.parse',fromlist=['parse_qsl']).parse_qsl(parsed.query) if not k.startswith('utm_')]
        return urlunparse((parsed.scheme,parsed.netloc,parsed.path,parsed.params,urlencode(query),""))
    except ValueError:
        return ""

def main():
    names = []
    if (BASE / 'indicacoes.csv').exists():
        df = pd.read_csv(BASE / 'indicacoes.csv', dtype=str).fillna('')
        names = sorted({clean(n) for n in df.get('nome', []) if len(clean(n).split()) >= 2})
    old = []
    if OUTPUT.exists():
        with OUTPUT.open(encoding='utf-8-sig', newline='') as f:
            old = list(csv.DictReader(f))
    seen = {normalized_url(row.get('url')) for row in old}
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    new = []
    failures = []
    for query in QUERIES:
        rss = 'https://news.google.com/rss/search?q=' + quote_plus(query + ' when:7d') + '&hl=pt-BR&gl=BR&ceid=BR:pt-419'
        try:
            resp = requests.get(rss, timeout=20, headers={'User-Agent': 'RadarDaEsplanada/1.0 (RSS research)'})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if feed.bozo and not feed.entries:
                raise ValueError('RSS inválido')
            for entry in feed.entries[:70]:
                title = clean(entry.get('title'))
                link = normalized_url(entry.get('link'))
                if not title or not link or link in seen:
                    continue
                source = entry.get('source', {})
                vehicle = clean(source.get('title') if hasattr(source,'get') else '')
                if not vehicle and ' - ' in title:
                    title, vehicle = title.rsplit(' - ', 1)
                snippet = clean(entry.get('summary'))
                mentioned = [n for n in names if re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', title+' '+snippet, re.I)]
                new.append({'titulo': title, 'veiculo': vehicle, 'data_publicacao': clean(entry.get('published')),
                            'url': link, 'busca': query, 'nomes_mencionados': '; '.join(mentioned), 'capturado_em': now})
                seen.add(link)
        except (requests.RequestException, ValueError) as exc:
            failures.append(f'{query}: {type(exc).__name__}: {str(exc)[:120]}')
        time.sleep(0.2)
    all_rows = (new + old)[:MAX_ROWS]
    tmp = OUTPUT.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader(); writer.writerows(all_rows)
    os.replace(tmp, OUTPUT)
    STATUS.write_text(json.dumps({'ultima_tentativa_utc':now, 'novas_noticias':len(new),
                                  'total_armazenado':len(all_rows), 'consultas':len(QUERIES),
                                  'falhas':failures, 'fontes':'Google News RSS (agregador; não cobre toda a imprensa)'},
                                 ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(new)} notícias novas; {len(all_rows)} no histórico; {len(failures)} falhas')
    if len(failures) == len(QUERIES):
        raise RuntimeError('Todas as consultas RSS falharam')

if __name__ == '__main__':
    main()
