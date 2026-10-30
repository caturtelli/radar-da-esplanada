from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

def test_home_cards_and_round_trip():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=120).run()
    assert not app.exception
    assert app.radio[0].value=='Ministérios e órgãos'
    cards=[b for b in app.button if b.key and b.key.startswith('open_org_')]
    assert len(cards)==31
    assert not any(h.value=='Ministério da Agricultura e Pecuária' for h in app.subheader)
    app.button(key='open_org_Ministério da Fazenda').click().run()
    assert not app.exception
    assert any(h.value=='Ministério da Fazenda' for h in app.subheader)
    assert any('Rafael Fonteles' in h.value for h in app.markdown)
    app.button(key='org_person_Rafael Fonteles').click().run()
    assert not app.exception
    assert app.radio[0].value=='Pessoas'
    assert app.selectbox(key='person_choice').value=='Rafael Fonteles'
    app.radio[0].set_value('Ministérios e órgãos').run()
    app.button(key='back_org').click().run()
    assert not app.exception
    assert len([b for b in app.button if b.key and b.key.startswith('open_org_')])==31
    app.radio(key='org_category').set_value('Todos os 79 órgãos').run()
    assert not app.exception
    assert len([b for b in app.button if b.key and b.key.startswith('open_org_')])==79
    for view in ['Pessoas','Últimas movimentações','Todas as notícias','Cadastro editorial']:
        app.radio[0].set_value(view).run()
        assert not app.exception,view
    app.sidebar.text_input[0].set_value('Haddad').run()
    assert not app.exception
