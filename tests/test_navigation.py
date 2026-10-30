from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from navigation import Route,decode_route,route_params,slug_map
from streamlit.testing.v1 import AppTest

ORGS=['Ministério da Fazenda','Casa Civil','Ministério da Justiça e Segurança Pública']
PEOPLE=['Rafael Fonteles','Márcio Tavares']

def test_readable_routes_and_round_trip():
    route=Route(org=ORGS[0])
    assert route_params(route,ORGS,PEOPLE)=={'orgao':'fazenda'}
    route=Route(view='Pessoas',person='Rafael Fonteles',page=3)
    params=route_params(route,ORGS,PEOPLE,{'utm_source':'teste','orgao':'fazenda','pagina':'2'})
    assert params=={'utm_source':'teste','pessoa':'rafael-fonteles','pagina':'3'}
    assert decode_route(params,ORGS,PEOPLE)==(route,'')
    assert route_params(Route(),ORGS,PEOPLE,params)=={'utm_source':'teste'}

def test_bad_and_repeated_parameters_are_safe():
    assert decode_route({'orgao':'inexistente'},ORGS,PEOPLE)[1]
    route,warning=decode_route({'pessoa':'inexistente'},ORGS,PEOPLE)
    assert route.person is None and warning
    assert decode_route({'tela':'noticias','pagina':'-5'},ORGS,PEOPLE)[0].page==1
    assert decode_route({'tela':'noticias','pagina':'abc'},ORGS,PEOPLE)[0].page==1
    assert decode_route({'orgao':['inexistente','fazenda']},ORGS,PEOPLE)[0].org==ORGS[0]
    names=['Márcio Tavares','Marcio Tavares']
    assert len(slug_map(names))==2
    assert slug_map(names)==slug_map(list(reversed(names)))

def app():
    return AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=120)

def test_navigation_links_back_forward_reload_and_pagination():
    a=app().run()
    assert not a.exception
    assert not a.query_params
    a.button(key='open_org_Ministério da Fazenda').click().run()
    assert not a.exception
    assert a.query_params['orgao']==['fazenda'] or a.query_params['orgao']=='fazenda'
    org_params=dict(a.query_params)
    a.button(key='org_person_Rafael Fonteles').click().run()
    assert not a.exception
    assert a.selectbox(key='person_choice').value=='Rafael Fonteles'
    person_params=dict(a.query_params)
    assert 'pessoa' in person_params and 'orgao' not in person_params
    # Browser popstate sends the previous query to Streamlit: URL wins over stale widgets.
    a.query_params.clear();a.query_params.update(org_params);a.run()
    assert not a.exception
    assert a.radio(key='radar_view').value=='Ministérios e órgãos'
    assert any(h.value=='Ministério da Fazenda' for h in a.subheader)
    a.query_params.clear();a.run()
    assert not a.exception
    assert len([b for b in a.button if b.key and b.key.startswith('open_org_')])==31
    a.query_params.update(person_params);a.run()
    assert not a.exception
    assert a.selectbox(key='person_choice').value=='Rafael Fonteles'
    # A copied URL works in a brand new session, with no session_state from the sender.
    fresh=app();fresh.query_params.update(person_params);fresh.run()
    assert not fresh.exception
    assert fresh.selectbox(key='person_choice').value=='Rafael Fonteles'
    a.radio(key='radar_view').set_value('Todas as notícias').run()
    assert not a.exception
    a.number_input(key='news').set_value(2).run()
    assert not a.exception
    assert str(a.query_params['pagina']).strip("[]'")== '2'
    a.query_params['pagina']='1';a.run()
    assert not a.exception
    assert a.number_input(key='news').value==1

def test_invalid_link_does_not_reopen_previous_detail():
    a=app();a.query_params['orgao']='fazenda';a.run()
    a.query_params['orgao']='nao-existe';a.run()
    assert not a.exception
    assert len([b for b in a.button if b.key and b.key.startswith('open_org_')])==31
