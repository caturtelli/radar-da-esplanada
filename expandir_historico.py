"""Busca complementar por todos os órgãos. Não muda os workflows existentes.
Execute: python expandir_historico.py --inicio 2026-10-25 --fim 2026-10-30
Preserva todas as linhas e colunas do histórico; relatório próprio de cobertura.
"""
import argparse
import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo
import feedparser
import requests
from coletar_noticias import clean, normalized_url, FIELDS, QUERIES

BASE=Path(__file__).resolve().parent

def organ_queries(catalog):
    queries=[]
    for row in catalog:
        org=row['orgao']
        # Full official name plus the commonly used short designation.
        import re
        short=re.sub(r'^Ministério (?:da |das |do |dos |de )?', '', org)
        query=f'"Lula" ("{org}" OR "{short}") (ministro OR cotado OR nomeação OR convite OR presidência OR indicação OR governo)'
        queries.append((org,query))
    queries.extend(('Governo — busca geral',q) for q in QUERIES)
    queries.extend(('Governo — busca geral',q) for q in ['"Lula" "novo governo" ministros', '"Lula" "reforma ministerial"','"Lula" "cotados"','"Lula" "equipe ministerial"'])
    return queries

def collect_query(job, start, end):
    organ,query=job
    terms=f'{query} after:{(start-timedelta(days=1)).isoformat()} before:{(end+timedelta(days=1)).isoformat()}'
    url='https://news.google.com/rss/search?q='+quote_plus(terms)+'&hl=pt-BR&gl=BR&ceid=BR:pt-419'
    report={'orgao':organ,'consulta':query,'inicio':str(start),'fim':str(end),'encontradas':0,'saturada':False,'falha':''}
    try:
        response=requests.get(url,timeout=20,headers={'User-Agent':'RadarDaEsplanada/2.0 (RSS research)'})
        response.raise_for_status()
        feed=feedparser.parse(response.content)
        if feed.bozo and not feed.entries: raise ValueError('RSS inválido')
        report['saturada']=len(feed.entries)>=100
        rows=[]
        for entry in feed.entries:
            try:
                published=parsedate_to_datetime(entry.get('published',''))
                if published.tzinfo is None: published=published.replace(tzinfo=timezone.utc)
            except (ValueError,TypeError,IndexError): continue
            local=published.astimezone(ZoneInfo('America/Sao_Paulo'))
            if not start<=local.date()<=end: continue
            if local.date()==date(2026,10,25) and local.hour<17: continue
            title=clean(entry.get('title'))
            link=normalized_url(entry.get('link'))
            if not title or not link:continue
            source=entry.get('source',{})
            vehicle=clean(source.get('title','')) if hasattr(source,'get') else ''
            rows.append(dict(titulo=title,veiculo=vehicle,data_publicacao=clean(entry.get('published')),
                url=link,busca=query,nomes_mencionados='',capturado_em=datetime.now(timezone.utc).isoformat(timespec='seconds')))
        report['encontradas']=len(rows)
        return rows,report
    except (requests.RequestException,ValueError) as exc:
        report['falha']=f'{type(exc).__name__}: {exc}'
        return [],report

def merge_history(existing,new):
    combined=list(existing)
    seen={normalized_url(r.get('url','')) for r in existing if normalized_url(r.get('url',''))}
    for row in new:
        link=normalized_url(row.get('url',''))
        if link and link not in seen:
            combined.append(row);seen.add(link)
    return combined

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--inicio',type=date.fromisoformat,default=date(2026,10,25))
    parser.add_argument('--fim',type=date.fromisoformat,default=datetime.now(ZoneInfo('America/Sao_Paulo')).date())
    parser.add_argument('--diretorio',type=Path,default=BASE)
    args=parser.parse_args()
    if args.fim<args.inicio:parser.error('Fim anterior ao início')
    root=args.diretorio
    with (root/'catalogo_orgaos.csv').open(encoding='utf-8-sig') as f: catalog=list(csv.DictReader(f))
    path=root/'noticias_coletadas.csv'
    existing=[]
    fields=list(FIELDS)
    if path.exists():
        with path.open(encoding='utf-8-sig') as f:
            reader=csv.DictReader(f);fields=list(dict.fromkeys((reader.fieldnames or [])+FIELDS));existing=list(reader)
    jobs=organ_queries(catalog)
    reports=[];new=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows,report in pool.map(lambda job:collect_query(job,args.inicio,args.fim),jobs):
            new.extend(rows);reports.append(report)
            print(f'{report["orgao"]}: {len(rows)} notícia(s)'+(' — FALHA' if report['falha'] else ''),flush=True)
    # Queries hitting the RSS cap get a second pass by day.
    saturated=[(r['orgao'],r['consulta']) for r in reports if r['saturada']]
    extra=[(job,args.inicio+timedelta(days=i)) for job in saturated for i in range((args.fim-args.inicio).days+1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows,report in pool.map(lambda v:collect_query(v[0],v[1],v[1]),extra):new.extend(rows);reports.append(report)
    if all(r['falha'] for r in reports):raise RuntimeError('Todas as buscas falharam. Histórico intocado.')
    combined=merge_history(existing,new)
    tmp=path.with_suffix('.expansao.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(combined)
    os.replace(tmp,path)
    report={'executado_em':datetime.now(timezone.utc).isoformat(),'inicio':str(args.inicio),'fim':str(args.fim),
            'orgaos_consultados':len(catalog),'antes':len(existing),'novas':len(combined)-len(existing),'total':len(combined),
            'falhas':sum(bool(r['falha']) for r in reports),'consultas':reports,
            'limite':'RSS não garante cobertura integral; buscas sem resultados não provam ausência de notícias.'}
    (root/'cobertura_historica.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='consultas'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
