import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
import app as mod
client=TestClient(mod.app)

def test_health():
    assert client.get('/api/health').status_code==200

def test_settings_save_without_key():
    original=mod.DB_PATH
    with tempfile.TemporaryDirectory() as d:
        mod.DB_PATH=Path(d)/'test.db';mod.init_db()
        res=client.post('/api/settings',json={'base_url':'https://example.test/v1','model':'mock-model','language':'hinglish','verification_depth':'deep','evidence_budget':'6'})
        assert res.status_code==200;data=res.json()
        assert data['model']=='mock-model' and data['language']=='hinglish'
        assert data['verification_depth']=='deep' and data['evidence_budget']=='6'
        assert 'api_key' not in data
    mod.DB_PATH=original

def test_stability_live_conditions(monkeypatch):
    original=mod.DB_PATH
    with tempfile.TemporaryDirectory() as d:
        mod.DB_PATH=Path(d)/'stability.db';mod.init_db()
        async def mock_llm(messages,max_tokens=1800): return 'A mock controlled response.'
        monkeypatch.setattr(mod,'llm',mock_llm)
        res=client.post('/api/stability/run',json={'topic':'A testable claim about city air quality'})
        assert res.status_code==200;data=res.json()
        assert len(data['conditions'])==4
        assert data['metrics']['baseline_paraphrase_token_jaccard_percent']==100.0
        assert 'not accuracy measurements' in data['label'].lower()
        assert len(client.get('/api/stability/history').json())==1
    mod.DB_PATH=original

def test_history_empty_shape():
    res=client.get('/api/history');assert res.status_code==200 and isinstance(res.json(),list)

def test_html_has_all_pages():
    html=client.get('/').text
    for page in ['overview','workspace','verification','evidence','stability','history','settings']:
        assert f'id="page-{page}"' in html

def test_hindi_query_pipeline_three_stages(monkeypatch):
    original=mod.DB_PATH
    with tempfile.TemporaryDirectory() as d:
        mod.DB_PATH=Path(d)/'query.db';mod.init_db()
        calls=[]
        outputs=[
            'Initial Hindi draft',
            '{"intent_summary":"Test intent","claims":[{"claim":"कथन","assessment":"not_checked","explanation":"External evidence not retrieved","source_indices":[]}],"challenge":"No supporting sources available","revision_summary":"Qualified pending sources","limitations":["Search not configured"]}',
            '{"final_answer":"उत्तर को सावधानी से लें; बाहरी स्रोत जाँचे नहीं गए।","decision":"QUALIFY","confidence_label":"low","revision_summary":"क्योंकि स्रोत उपलब्ध नहीं थे, उत्तर qualify किया गया।","limitations":["No external sources"]}'
        ]
        async def mock_llm(messages,max_tokens=1800):
            calls.append(messages)
            return outputs.pop(0)
        monkeypatch.setattr(mod,'llm',mock_llm)
        res=client.post('/api/query',json={'query':'Hindi में test सवाल','language':'auto','depth':'balanced','evidence_budget':2,'search_enabled':False})
        assert res.status_code==200
        data=res.json();assert data['report']['decision']=='QUALIFY'
        assert data['report']['claims'][0]['claim']=='कथन'
        assert len(calls)==3 and len(data['stages_completed'])==4
    mod.DB_PATH=original

def test_provider_connection_test(monkeypatch):
    async def mock_llm(messages,max_tokens=1800): return 'EVIDENT_CONNECTION_OK'
    monkeypatch.setattr(mod,'llm',mock_llm)
    result=client.post('/api/settings/test',json={}).json()
    assert result['connected'] is True
