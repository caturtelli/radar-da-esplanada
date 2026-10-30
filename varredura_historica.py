"""Varredura pontual: 26/10/2026 até hoje; não altera a coleta agendada."""
import csv
import os
import re
import time
from datetime import datetime, timezone, date
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
import feedparser
import requests
from coletar_noticias import BASE, OUTPUT, FIELDS, QUERIES, MAX_ROWS, clean, normalized_url

START = date(2026, 10, 26)
EXTRA_QUERIES = [
    '"Lula" "novo governo" ministros',
    '"Lula" "reforma ministerial"',
    '"Lula" "cotado" ministério',
    '"Lula" "convite" ministro',
    '"Lula" "equipe ministerial"',
    '"Lula" "PSD" ministério',
    '"Lula" "MDB" ministério',
    '"Lula" "União Brasil" ministério',
    '"Lula" "PP" ministério',
    '"Lula" "presidência" estatal',
]

def publication_date(entry):
    raw = entry.get('published') or entry.get('updated') or ''
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except (TypeError, ValueError, IndexError):
        return None

def main():
    today = datetime.now(timezone.utc).date()
    if today < START:
        raise RuntimeError('A data inicial está no futuro.')
    existing = []
    if OUTPUT.exists():
        with OUTPUT.open(encoding='utf-8-sig', newline='') as handle:
            existing = list(csv.DictReader(handle))
    seen = {normalized_url(row.get('url')) for row in existing}
    new = []
    failures = []
    no_date = 0
    queries = list(dict.fromkeys(QUERIES + EXTRA_QUERIES))
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    # before: é exclusivo. Dia seguinte à data atual inclui o dia de hoje.
    from datetime import timedelta
    before = (today + timedelta(days=1)).isoformat()
    for query in queries:
        terms = f'{query} after:2026-10-25 before:{before}'
        url = 'https://news.google.com/rss/search?q=' + quote_plus(terms) + '&hl=pt-BR&gl=BR&ceid=BR:pt-419'
        try:
            resp = requests.get(url, timeout=25, headers={'User-Agent': 'RadarDaEsplanada/1.0 (RSS research)'})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if feed.bozo and not feed.entries:
                raise ValueError('RSS inválido')
            for entry in feed.entries[:100]:
                day = publication_date(entry)
                if day is None:
                    no_date += 1
                    continue
                if not (START <= day <= today):
                    continue
                title = clean(entry.get('title'))
                link = normalized_url(entry.get('link'))
                if not title or not link or link in seen:
                    continue
                source = entry.get('source', {})
                vehicle = clean(source.get('title') if hasattr(source, 'get') else '')
                if not vehicle and ' - ' in title:
                    title, vehicle = title.rsplit(' - ', 1)
                new.append({'titulo': title, 'veiculo': vehicle,
                            'data_publicacao': clean(entry.get('published')),
                            'url': link, 'busca': query,
                            'nomes_mencionados': '', 'capturado_em': now})
                seen.add(link)
        except (requests.RequestException, ValueError) as exc:
            failures.append(f'{query}: {type(exc).__name__}: {str(exc)[:120]}')
        time.sleep(0.2)
    if len(failures) == len(queries):
        raise RuntimeError('Todas as consultas falharam; histórico preservado.')
    # Preserva as matérias já coletadas. Sem apagar linhas antigas.
    combined = existing + new
    if len(combined) > MAX_ROWS:
        print(f'ATENÇÃO: limite de {MAX_ROWS} linhas atingido; nenhuma linha antiga será apagada.')
        combined = existing + new[:max(0, MAX_ROWS - len(existing))]
    tmp = OUTPUT.with_suffix('.historico.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(combined)
    os.replace(tmp, OUTPUT)
    print(f'Varredura de {START} a {today}: {len(new)} notícias novas, {len(combined)} armazenadas, {len(failures)} consultas falharam, {no_date} entradas sem data descartadas.')
    for f in failures:
        print('FALHA:', f)

if __name__ == '__main__':
    main()
