import csv
import json
from pathlib import Path
import pandas as pd
import pytest
from coletar_noticias import collect, periodic_queries, FIELDS
from radar_model import build_index, minister_candidates, read_csv

BASE = Path(__file__).resolve().parents[1]
CATALOG = read_csv(BASE, 'catalogo_orgaos.csv')

def candidates(*titles):
    rows = build_index(pd.DataFrame([dict(titulo=t, url=f'https://test/{i}', data_publicacao=f'2026-11-0{i+1}T12:00:00Z') for i,t in enumerate(titles)]),pd.DataFrame(),CATALOG)
    return minister_candidates(rows,CATALOG,now=pd.Timestamp('2026-11-06T15:00:00Z'))

def test_minister_highlight_scopes_office_subject_and_person():
    result=candidates('Rafael Fonteles é cotado para ministro da Fazenda; Camilo Santana é cotado para secretário-executivo do Ministério da Educação')
    assert [(c['nome'],c['orgao']) for c in result]==[('Rafael Fonteles','Ministério da Fazenda')]
    assert not candidates('Rodrigo Pacheco é cotado para ministro do Supremo')
    assert not candidates('Fernando Haddad comenta medidas no Ministério da Fazenda')
    assert not candidates('Reeleição de Hugo Motta pode levar alagoano a ser ministro de Lula')
    assert not candidates('Sucessão de Múcio na Defesa tem três nomes cotados')
    assert not candidates('Lula deve manter Margareth Menezes na Cultura apesar de nomes cotados para o ministério')
    assert not candidates('Pedro Lupion rejeita indicação para ministro da Agricultura')
    assert not candidates('Rafael Fonteles é cotado para governador')
    assert candidates('Daniella Ribeiro é cotada para ser ministra no governo Lula')[0]['orgao']=='Pasta não informada'
    assert candidates('Carlos Fávaro pode voltar a ser ministro da Agricultura')[0]['orgao']=='Ministério da Agricultura e Pecuária'
    pair=candidates('Wagner Moura e Maria Marighella são cotados para Ministério da Cultura')
    assert {c['nome'] for c in pair}=={'Wagner Moura','Maria Marighella'}

def test_newer_denial_or_appointment_removes_candidate_without_crossing_orgs():
    first='Rafael Fonteles é cotado para ministro da Fazenda'
    assert not candidates(first,'Rafael Fonteles nega convite para Ministério da Fazenda')
    assert not candidates(first,'Rafael Fonteles foi nomeado ministro da Fazenda')
    result=candidates(first,'Rafael Fonteles nega convite para Ministério da Educação')
    assert result[0]['orgao']=='Ministério da Fazenda'
    assert not candidates(first,'Rafael Fonteles nega convite para ser ministro')
    assert candidates(first,'Rafael Fonteles comenta economia')

def test_periodic_queries_cover_all_catalog_organs():
    jobs=periodic_queries(CATALOG.to_dict('records'))
    assert set(CATALOG.orgao) <= {org for org,q in jobs}
    assert len(jobs)==89

def prepare(tmp_path):
    (tmp_path/'catalogo_orgaos.csv').write_text('orgao,categoria\nMinistério da Fazenda,Ministério\n',encoding='utf-8')
    path=tmp_path/'noticias_coletadas.csv'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS+['jornalista'])
        writer.writeheader()
        for i in range(5001):
            writer.writerow(dict(url=f'https://old/{i}',titulo='Preservar',capturado_em='2026-11-01T00:00:00Z',data_publicacao='2026-10-30T00:00:00Z',jornalista='Autora'))
    return path

def response(job,rows=(),fail=''):
    return list(rows),dict(orgao=job[0],consulta=job[1],encontradas=len(rows),saturada=False,falha=fail)

def test_collection_preserves_history_columns_and_last_discovery_on_empty_runs(tmp_path):
    path=prepare(tmp_path)
    row=dict(url='https://new/1?utm_source=x',titulo='Nova',data_publicacao='2026-11-06T10:00:00Z')
    status=collect(tmp_path,lambda job:response(job,[row]))
    assert status['novas_noticias']==1 and status['total_armazenado']==5002
    data=pd.read_csv(path).fillna('')
    assert len(data)==5002 and data.iloc[-1].jornalista=='Autora'
    assert data.iloc[0].url=='https://new/1'
    before=path.read_bytes()
    empty=collect(tmp_path,lambda job:response(job))
    assert path.read_bytes()==before
    assert empty['novas_noticias']==0
    assert empty['ultima_noticia_encontrada_utc']==status['ultima_noticia_encontrada_utc']
    assert empty['ultima_publicacao_utc']=='2026-11-06T10:00:00+00:00'
    assert empty['consultas_com_sucesso']==empty['consultas']
    assert empty['ultima_coleta_completa_utc']

def test_total_failure_records_status_keeps_history_and_last_success(tmp_path):
    path=prepare(tmp_path)
    collect(tmp_path,lambda job:response(job))
    before=path.read_bytes()
    previous=json.loads((tmp_path/'status_coleta.json').read_text())
    with pytest.raises(RuntimeError):
        collect(tmp_path,lambda job:response(job,fail='timeout'))
    status=json.loads((tmp_path/'status_coleta.json').read_text())
    assert path.read_bytes()==before
    assert status['falhas'] and status['consultas_com_sucesso']==0
    assert status['ultima_coleta_sucesso_utc']==previous['ultima_coleta_sucesso_utc']
    assert status['ultima_coleta_completa_utc']==previous['ultima_coleta_completa_utc']

def test_partial_failure_is_visible(tmp_path):
    prepare(tmp_path)
    status=collect(tmp_path,lambda job:response(job,fail='timeout' if job[0]=='Ministério da Fazenda' else ''))
    assert len(status['falhas'])==1
    assert status['consultas_com_sucesso']==status['consultas']-1
    assert status['ultima_coleta_completa_utc'] is None
