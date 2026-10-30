from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from identificar_nomes import find_people, registry, status_from_title
from classificar_noticias import associate
from radar_model import build_index, read_csv, filter_rows, is_recent

BASE=Path(__file__).resolve().parents[1]

def test_all_79_organs():
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    assert len(catalog)==79
    for org in catalog.orgao:
        assert org in associate('Maria Oliveira foi convidada para '+org,catalog.orgao)

def test_identity_variants_and_ambiguity():
    known=registry(['Marina Oliveira é cotada para a Anvisa'])
    assert 'Marina Oliveira' in find_people('Oliveira nega convite',known)
    assert not find_people('Oliveira nega convite',['Marina Oliveira','Carla Oliveira'])
    assert 'Fernando Haddad' in find_people('Haddad comenta economia')
    assert 'Camilo Santana' in find_people('Camilo visita escola')
    assert not find_people('Haddadson comenta economia')

def test_mentions_and_modalities():
    assert status_from_title('Haddad comenta economia')=='Menção'
    assert status_from_title('Haddad pode ser nomeado')=='Especulação'
    assert status_from_title('Haddad não foi nomeado')=='Negativa'
    assert status_from_title('Haddad foi nomeado')=='Nomeação noticiada'
    assert status_from_title('Haddad foi convidado')=='Convite noticiado'
    assert status_from_title('Haddad negocia ida para Fazenda')=='Negociação'

def test_person_and_org_scoping():
    title='Fernando Haddad nega convite para Ministério da Fazenda; Camilo Santana foi convidado para Ministério da Educação'
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    row=build_index(pd.DataFrame([{'titulo':title,'url':'https://a.test/1'}]),pd.DataFrame(),catalog)[0]
    assert row['estados']['Camilo Santana']=='Convite noticiado'
    assert row['estados']['Fernando Haddad']=='Negativa'
    assert row['vinculos']['Camilo Santana']==['Ministério da Educação']
    assert row['vinculos']['Fernando Haddad']==['Ministério da Fazenda']

def test_news_dates_and_republication():
    now=pd.Timestamp('2026-10-30T15:00:00Z')
    assert is_recent({'data_publicacao':'2026-10-30T14:00:00Z'},now)
    assert not is_recent({'data_publicacao':'2026-10-31T14:00:00Z'},now)
    assert not is_recent({'data_publicacao':'','capturado_em':'2026-10-30T14:00:00Z'},now)
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    rows=build_index(pd.DataFrame([{'titulo':'Haddad nega convite','url':u} for u in ['https://a.test','https://b.test']]),pd.DataFrame(),catalog)
    assert rows[0]['grupo_republicacao']==rows[1]['grupo_republicacao']!=''
    assert len(filter_rows(rows,query='HADDAD',statuses=['Negativa']))==2

def test_real_history_read_only():
    before={p:p.read_bytes() for p in BASE.glob('*.csv')}
    rows=build_index(read_csv(BASE,'noticias_coletadas.csv'),read_csv(BASE,'indicacoes.csv'),read_csv(BASE,'catalogo_orgaos.csv'))
    assert rows
    assert all(p.read_bytes()==data for p,data in before.items())


def test_real_headline_and_generic_alias_regression():
    known=registry(['Para Giannetti, economia deve mudar', 'Aguinaldo Ribeiro é cotado para assumir Ministério de Portos e Aeroportos'])
    title='Aguinaldo Ribeiro é cotado para assumir Ministério de Portos e Aeroportos - Portal BE News'
    assert find_people(title,known)==['Aguinaldo Ribeiro']
    assert status_from_title(title,'Aguinaldo Ribeiro',known)=='Especulação'
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    row=build_index(pd.DataFrame([{'titulo':title}]),pd.DataFrame(),catalog)[0]
    assert row['vinculos']['Aguinaldo Ribeiro']==['Ministério de Portos e Aeroportos']
    assert 'Para Giannetti' not in known
    assert 'Paulo Silva' in registry(['Paulo Silva é cotado para Anvisa'])

def test_no_generic_entities_and_two_distinct_targets():
    known=registry(['Criminalista Pierpaolo Bottini é cotado para Ministério da Justiça','Nome de Wagner Moura surge para Ministério da Cultura','Equipe de Lula define Planos de Lula'])
    assert 'Pierpaolo Bottini' in known
    assert 'Wagner Moura' in known
    assert not any(n in known for n in ['Equipe de Lula','Planos de Lula','Criminalista Pierpaolo Bottini','Nome de Wagner Moura'])
    t='Rafael Fonteles é cotado para ministro da Fazenda e Camilo Santana para ministro-chefe da Casa Civil'
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    row=build_index(pd.DataFrame([{'titulo':t}]),pd.DataFrame(),catalog)[0]
    assert row['vinculos']['Rafael Fonteles']==['Ministério da Fazenda']
    assert row['vinculos']['Camilo Santana']==['Casa Civil']

def test_history_expansion_preserves_unknown_fields_and_queries_all_organs():
    from expandir_historico import merge_history,organ_queries
    old=[{'url':'https://a.test/x','titulo':'Original','jornalista':'Autora','extra':'preservar'}]
    combined=merge_history(old,[{'url':'https://a.test/x','titulo':'Repetida'},{'url':'https://b.test/y','titulo':'Nova'}])
    assert combined[0]==old[0]
    assert len(combined)==2
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    assert set(catalog.orgao).issubset({o for o,q in organ_queries(catalog.to_dict('records'))})

def test_second_round_cutoff():
    from radar_model import since_second_round
    assert not since_second_round({'data_publicacao':'2026-10-25T19:59:00Z'})
    assert since_second_round({'data_publicacao':'2026-10-25T20:01:00Z'})
    assert not since_second_round({'data_publicacao':''})


def test_lula_not_lula_da_fonte():
    assert not find_people('Lula avalia novo governo',['Lula da Fonte'])


def test_lawyers_client_is_not_candidate():
    t='Lula avalia ex-advogado de Daniel Vorcaro para assumir Ministério da Justiça'
    assert status_from_title(t,'Daniel Vorcaro',['Daniel Vorcaro'])=='Menção'


def test_real_corpus_names_in_multiple_ministries():
    from radar_model import organ_people
    catalog=read_csv(BASE,'catalogo_orgaos.csv')
    curated=read_csv(BASE,'indicacoes.csv')
    rows=build_index(read_csv(BASE,'noticias_coletadas.csv'),curated,catalog)
    for org,person in [('Ministério da Agricultura e Pecuária','Carlos Fávaro'),('Ministério da Justiça e Segurança Pública','Pierpaolo Bottini'),('Ministério das Mulheres','Erika Hilton'),('Ministério da Fazenda','Rafael Fonteles'),('Casa Civil','Camilo Santana')]:
        assert person in organ_people([r for r in rows if org in r['orgaos']],curated,org)
    justice=organ_people([r for r in rows if 'Ministério da Justiça e Segurança Pública' in r['orgaos']],curated,'Ministério da Justiça e Segurança Pública')
    assert 'Daniel Vorcaro' not in justice
