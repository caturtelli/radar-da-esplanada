"""Coleta periódica por órgão; matérias são pistas, não confirmações."""
import csv
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlunparse, urlencode, parse_qsl
import feedparser
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
FIELDS = ['titulo', 'veiculo', 'data_publicacao', 'url', 'busca', 'nomes_mencionados', 'capturado_em']
QUERIES = [
    '"Lula" "ministério" "nome"', '"Lula" "ministro" "indicação"',
    '"Lula" "secretário-executivo"', '"governo Lula" "nomeação"',
    '"Lula" "composição do governo"', '"Lula" "estatais" "presidência"',
]

def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def normalized_url(url):
    try:
        parsed = urlparse(clean(url))
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return ''
        query = [(k, v) for k, v in parse_qsl(parsed.query) if not k.startswith('utm_')]
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), ''))
    except ValueError:
        return ''

def periodic_queries(catalog):
    from expandir_historico import organ_queries
    return list(dict.fromkeys(organ_queries(catalog)))

def fetch_query(job):
    organ, query = job
    rss = 'https://news.google.com/rss/search?q=' + quote_plus(query + ' when:7d') + '&hl=pt-BR&gl=BR&ceid=BR:pt-419'
    report = {'orgao': organ, 'consulta': query, 'encontradas': 0, 'saturada': False, 'falha': ''}
    try:
        resp = requests.get(rss, timeout=20, headers={'User-Agent': 'RadarDaEsplanada/2.2 (RSS research)'})
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if not feed.get('version') or (feed.bozo and not feed.entries):
            raise ValueError('RSS inválido')
        rows = []
        for entry in feed.entries:
            title, link = clean(entry.get('title')), normalized_url(entry.get('link'))
            if not title or not link:
                continue
            source = entry.get('source', {})
            vehicle = clean(source.get('title') if hasattr(source, 'get') else '')
            if not vehicle and ' - ' in title:
                title, vehicle = title.rsplit(' - ', 1)
            rows.append(dict(titulo=title, veiculo=vehicle, data_publicacao=clean(entry.get('published')),
                             url=link, busca=query, nomes_mencionados=''))
        report.update(encontradas=len(rows), saturada=len(feed.entries) >= 100)
        return rows, report
    except (requests.RequestException, ValueError) as exc:
        report['falha'] = f'{type(exc).__name__}: {str(exc)[:160]}'
        return [], report

def latest_timestamp(rows, field):
    dates = pd.to_datetime([r.get(field, '') for r in rows], errors='coerce', utc=True, format='mixed')
    valid = dates[dates.notna()]
    return valid.max().isoformat() if len(valid) else None

def collect(base=BASE, fetcher=fetch_query):
    base = Path(base)
    output, status_path = base / 'noticias_coletadas.csv', base / 'status_coleta.json'
    with (base / 'catalogo_orgaos.csv').open(encoding='utf-8-sig', newline='') as f:
        catalog = list(csv.DictReader(f))
    if not catalog:
        raise ValueError('Catálogo de órgãos vazio')
    old, fields = [], list(FIELDS)
    if output.exists():
        with output.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            fields = list(dict.fromkeys((reader.fieldnames or []) + FIELDS))
            old = list(reader)
    try:
        previous = json.loads(status_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        previous = {}
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    jobs = periodic_queries(catalog)
    reports, candidates = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows, report in pool.map(fetcher, jobs):
            reports.append(report)
            candidates.extend(rows)
    finished = datetime.now(timezone.utc).isoformat(timespec='seconds')
    seen = {normalized_url(row.get('url')) for row in old}
    new = []
    for row in candidates:
        link = normalized_url(row.get('url'))
        if not link or link in seen:
            continue
        seen.add(link)
        new.append(dict(row, url=link, capturado_em=finished))
    all_rows = new + old
    failures = [r['orgao'] + ': ' + r['falha'] for r in reports if r['falha']]
    succeeded = len(reports) - len(failures)
    # Preserve all historical rows and unknown columns, without a retention cap.
    if new or (succeeded and not output.exists()):
        tmp = output.with_suffix('.tmp')
        with tmp.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_rows)
        os.replace(tmp, output)
    status = {
        'ultima_tentativa_utc': started, 'concluida_em_utc': finished,
        'ultima_coleta_sucesso_utc': finished if succeeded else previous.get('ultima_coleta_sucesso_utc'),
        'ultima_coleta_completa_utc': finished if not failures else previous.get('ultima_coleta_completa_utc'),
        'ultima_noticia_encontrada_utc': latest_timestamp(all_rows, 'capturado_em') or previous.get('ultima_noticia_encontrada_utc'),
        'ultima_publicacao_utc': latest_timestamp(all_rows, 'data_publicacao'),
        'novas_noticias': len(new), 'total_armazenado': len(all_rows),
        'orgaos_consultados': len(catalog), 'consultas': len(jobs), 'consultas_com_sucesso': succeeded,
        'falhas': failures, 'consultas_saturadas': sum(r['saturada'] for r in reports),
        'detalhes_consultas': reports, 'frequencia_prevista_minutos': 30,
        'fontes': 'Google News RSS (agregador; não cobre toda a imprensa)',
    }
    tmp = status_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, status_path)
    print(f'{len(new)} notícias novas; {len(all_rows)} no histórico; {len(failures)} falhas; {len(catalog)} órgãos')
    if not succeeded:
        raise RuntimeError('Todas as consultas RSS falharam; histórico preservado')
    return status

if __name__ == '__main__':
    collect()
