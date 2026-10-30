from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

def test_all_views_and_filters():
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=120).run()
    assert not app.exception
    assert app.sidebar.radio[0].value=='Ministérios e órgãos'
    for view in ['Pessoas','Últimas movimentações','Todas as notícias','Cadastro editorial','Ministérios e órgãos']:
        app.sidebar.radio[0].set_value(view).run()
        assert not app.exception, view
    app.sidebar.text_input[0].set_value('Haddad').run()
    assert not app.exception
    app.sidebar.checkbox[0].check().run()
    assert not app.exception
