from __future__ import annotations
import os, sqlite3, json, re, time, asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
import httpx
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DB_PATH = ROOT / 'evident.db'
app = FastAPI(title='Evident Engine', version='1.0.0')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=12000)
    language: Literal['auto','hindi','hinglish','english'] = 'auto'
    depth: Literal['quick','balanced','deep'] = 'balanced'
    evidence_budget: int = Field(default=4, ge=1, le=8)
    search_enabled: bool = True

class SettingsRequest(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    language: str | None = None
    verification_depth: str | None = None
    evidence_budget: int | None = None
    search_enabled: bool | None = None


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            query TEXT NOT NULL, language TEXT NOT NULL, status TEXT NOT NULL,
            response TEXT, payload TEXT NOT NULL
        )''')
        con.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        con.execute('''CREATE TABLE IF NOT EXISTS stability_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, topic TEXT NOT NULL, output TEXT NOT NULL)''')
init_db()

DEFAULT_SETTINGS = {
    'base_url': os.getenv('AI_BASE_URL','https://api.openai.com/v1'),
    'api_key': os.getenv('AI_API_KEY',''),
    'model': os.getenv('AI_MODEL','gpt-4o-mini'),
    'language': 'auto',
    'verification_depth': 'balanced',
    'evidence_budget': '4',
}
def get_settings():
    s = DEFAULT_SETTINGS.copy()
    with db() as con:
        for row in con.execute('SELECT key,value FROM settings'):
            s[row['key']] = row['value']
    # Never expose secret key to browser
    s['api_key_configured'] = bool(s.get('api_key'))
    s.pop('api_key',None)
    s['search_configured'] = bool(os.getenv('TAVILY_API_KEY'))
    return s

async def llm(messages: list[dict[str,str]], max_tokens=1800):
    with db() as con:
        overrides = {r['key']: r['value'] for r in con.execute('SELECT key,value FROM settings')}
    base = overrides.get('base_url', DEFAULT_SETTINGS['base_url']).strip().rstrip('/')
    key = overrides.get('api_key', DEFAULT_SETTINGS['api_key'])
    model = overrides.get('model', DEFAULT_SETTINGS['model']).strip()
    if not base or not key or not model:
        raise HTTPException(400, 'AI provider is not configured. Add API endpoint, API key, and model in Settings.')
    try:
        async with httpx.AsyncClient(timeout=75) as client:
            r = await client.post(base + '/chat/completions', headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'}, json={'model':model,'messages':messages,'temperature':0.2,'max_tokens':max_tokens})
        if r.status_code >= 400:
            raise HTTPException(502, f'Provider error ({r.status_code}): {r.text[:500]}')
        return r.json()['choices'][0]['message']['content']
    except httpx.RequestError as e:
        raise HTTPException(502, f'AI provider connection failed: {e.__class__.__name__}')

async def search_evidence(query: str, budget: int):
    key = os.getenv('TAVILY_API_KEY','').strip()
    if not key: return [], 'Search not configured (optional TAVILY_API_KEY missing).'
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.post('https://api.tavily.com/search', json={'api_key':key,'query':query,'search_depth':'advanced','max_results':max(1,min(budget,8)),'include_answer':False})
        r.raise_for_status()
        results = r.json().get('results',[])
        evidence = []
        for x in results:
            url = x.get('url','')
            if urlparse(url).scheme not in ('http','https') or not urlparse(url).netloc:
                continue
            evidence.append({'title':x.get('title','Untitled'),'url':url,'content':x.get('content',''),'score':x.get('score')})
        return evidence, 'Tavily search returned sources.' if evidence else 'Search returned no sources.'
    except Exception as e:
        return [], f'Search failed: {e.__class__.__name__}'

@app.get('/')
def home():
    return HTMLResponse((ROOT/'static/index.html').read_text(encoding='utf-8'))
@app.get('/api/health')
def health():
    s=get_settings()
    return {'ok':True,'ai_configured':s['api_key_configured'],'search_configured':s['search_configured'],'version':'1.0.0'}
@app.get('/api/settings')
def settings(): return get_settings()
@app.post('/api/settings')
def save_settings(payload: dict[str,Any]):
    allowed={'base_url','api_key','model','language','verification_depth','evidence_budget'}
    with db() as con:
        for k,v in payload.items():
            if k in allowed and v is not None:
                con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
    return get_settings()
@app.post('/api/settings/test')
async def test_provider():
    try:
        answer=await llm([{'role':'system','content':'Return only the exact text: EVIDENT_CONNECTION_OK'},{'role':'user','content':'Connection test'}],max_tokens=30)
        if 'EVIDENT_CONNECTION_OK' not in answer: return {'connected':False,'message':'Endpoint responded, but test token did not match.'}
        return {'connected':True,'message':'Connection test successful. Model returned the expected token.'}
    except HTTPException as exc:
        return {'connected':False,'message':exc.detail}

@app.get('/api/history')
def history(limit:int=100):
    with db() as con:
        rows=con.execute('SELECT id,created_at,query,language,status,response FROM audit ORDER BY id DESC LIMIT ?', (max(1,min(limit,300)),)).fetchall()
    return [dict(r) for r in rows]
@app.get('/api/audit/{audit_id}')
def audit_detail(audit_id:int):
    with db() as con:
        row=con.execute('SELECT * FROM audit WHERE id=?',(audit_id,)).fetchone()
    if not row: raise HTTPException(404,'Audit record not found')
    d=dict(row); d['payload']=json.loads(d['payload']); d['payload']['id']=d['id']; return d

def parse_json_report(raw: str, fallback: dict[str, Any]):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match=re.search(r'\{.*\}',raw,re.S)
        if match:
            try: return json.loads(match.group(0))
            except json.JSONDecodeError: pass
    return fallback

@app.post('/api/query')
async def run_query(req:QueryRequest):
    started=time.time(); language=req.language or 'auto'
    evidence=[]; search_note='Search disabled by user.'
    if req.search_enabled:
        evidence,search_note=await search_evidence(req.query,req.evidence_budget)
    lang_rule={'auto':'Respond in the same language/script as the user query (Hindi, Hinglish/Roman Hindi, or English).','hindi':'Respond in Hindi (Devanagari).','hinglish':'Respond in Roman Hinglish.','english':'Respond in English.'}.get(language,'Respond in the same language/script as the user query.')
    context='\n\n'.join(f"[{i+1}] {e['title']}\nURL: {e['url']}\nSnippet: {e['content']}" for i,e in enumerate(evidence)) or 'No retrieved web evidence.'
    try:
        # Stage 1: independent first draft
        initial=await llm([{'role':'system','content':f'You are a helpful assistant. {lang_rule} Give a direct answer, clearly mention uncertainty, and do not claim external verification.'},{'role':'user','content':req.query}],max_tokens=1300)
        # Stage 2: independent evidence/claim review and critical challenge
        if req.depth in ('balanced','deep'):
            review_raw=await llm([{'role':'system','content':f'You are an independent answer auditor. {lang_rule} Inspect the user query and initial draft against the retrieved evidence. Do not treat the draft as truth. Break it into checkable factual claims, assess each as supported/partial/unsupported/contradicted/not_checked, explain briefly, and give a counter-challenge noting missing critical information, conflicts, and overconfidence. source_indices must refer to numbered sources only. Return valid JSON with keys: intent_summary, claims (array of claim, assessment, explanation, source_indices), challenge, revision_summary, limitations (array). Do not invent sources. Evidence: {context}'},{'role':'user','content':f'User query: {req.query}\n\nInitial draft:\n{initial}'}],max_tokens=1900)
            review=parse_json_report(review_raw,{'intent_summary':req.query,'claims':[],'challenge':'Structured review unavailable.','revision_summary':'No review available.','limitations':['Review stage returned unstructured output.']})
        else:
            review={'intent_summary':req.query,'claims':[],'challenge':'Quick mode skipped the independent challenge stage.','revision_summary':'Quick mode does not include claim-level review.','limitations':['Quick review mode skips independent claim assessment.']}
        # Stage 3: deep-only independent adversarial pass
        adversarial=''
        if req.depth=='deep':
            adversarial=await llm([{'role':'system','content':f'You are a critical challenger. {lang_rule} Try to find important weaknesses, alternative explanations, missing facts, or contradictions in the initial answer. Do not fabricate evidence. State when you cannot verify a challenge.'},{'role':'user','content':f'Question: {req.query}\nInitial draft: {initial}\nClaim review: {json.dumps(review,ensure_ascii=False)}\nEvidence snippets: {context}'}],max_tokens=900)
        # Stage 4: final synthesis
        final_raw=await llm([{'role':'system','content':f'Evident Engine final decision synthesizer. {lang_rule} Reconcile the initial draft, claim review, and available evidence. Be honest about search limitations. Output valid JSON keys: final_answer, decision (ACCEPT|REVISE|QUALIFY|ABSTAIN), confidence_label (low|medium|high), revision_summary, limitations (array). Never claim certainty or external verification without support. If no reliable evidence is available, qualify rather than falsely verify.'},{'role':'user','content':f'Question: {req.query}\nInitial draft:\n{initial}\nClaim review:\n{json.dumps(review,ensure_ascii=False)}\nAdditional adversarial review:\n{adversarial or "Not run in this depth setting."}\nEvidence:\n{context}'}],max_tokens=1700)
        final=parse_json_report(final_raw,{'final_answer':final_raw,'decision':'QUALIFY','confidence_label':'low','revision_summary':'Final output could not be parsed into structured decision; response is qualified.','limitations':['Structured final decision unavailable.']})
        data={'intent_summary':review.get('intent_summary',req.query),'initial_answer':initial,'claims':review.get('claims',[]),'challenge':(review.get('challenge','No challenge generated.')+('\n\nDeep adversarial pass:\n'+adversarial if adversarial else '')),'revision_summary':final.get('revision_summary',review.get('revision_summary','')),'final_answer':final.get('final_answer',initial),'decision':final.get('decision','QUALIFY'),'confidence_label':final.get('confidence_label','low'),'limitations':final.get('limitations',review.get('limitations',[]))}
        if not isinstance(data.get('final_answer'),str): data['final_answer']=str(data.get('final_answer') or initial)
        if not isinstance(data.get('initial_answer'),str): data['initial_answer']=str(data.get('initial_answer') or '')
        if not isinstance(data.get('challenge'),str): data['challenge']=str(data.get('challenge') or '')
        if not isinstance(data.get('revision_summary'),str): data['revision_summary']=str(data.get('revision_summary') or '')
        if not isinstance(data['claims'],list): data['claims']=[]
        if not isinstance(data['limitations'],list): data['limitations']=[str(data['limitations'])]
        if data['decision'] not in ('ACCEPT','REVISE','QUALIFY','ABSTAIN'): data['decision']='QUALIFY'
        if not evidence:
            if data['decision']=='ACCEPT': data['decision']='QUALIFY'
            caveats={'hindi':'इस रन में बाहरी स्रोत प्राप्त नहीं हुए; उत्तर मॉडल की सामान्य जानकारी पर आधारित है और बाहरी स्रोतों से सत्यापित नहीं है।','hinglish':'Is run mein external sources retrieve nahi hue; answer model ki general knowledge par based hai aur external sources se verify nahi hua.','english':'No external sources were retrieved in this run; this answer relies on model knowledge and is not externally source-verified.','auto':'No external sources were retrieved in this run; this answer relies on model knowledge and is not externally source-verified.'}
            caveat_language=language
            if language=='auto' and re.search(r'[\u0900-\u097f]',req.query): caveat_language='hindi'
            caveat=caveats.get(caveat_language,caveats['auto'])
            if caveat not in data['final_answer']: data['final_answer']=data['final_answer'].rstrip()+'\n\n'+caveat
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(500,f'Processing error: {e.__class__.__name__}')
    payload={'report':data,'evidence':evidence,'search_note':search_note,'duration_seconds':round(time.time()-started,2),'depth':req.depth,'budget':req.evidence_budget,'search_enabled':req.search_enabled,'stages_completed':['initial_draft','claim_review' if req.depth!='quick' else 'quick_mode_skip','adversarial_review' if req.depth=='deep' else 'deep_mode_skip','final_synthesis']}
    with db() as con:
        con.execute('INSERT INTO audit(created_at,query,language,status,response,payload) VALUES(?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),req.query,language,data['decision'],data['final_answer'],json.dumps(payload,ensure_ascii=False)))
        audit_id=con.execute('SELECT last_insert_rowid()').fetchone()[0]
    return {'id':audit_id,**payload}
@app.get('/api/stability/history')
def stability_history(limit:int=30):
    with db() as con:
        rows=con.execute('SELECT id,created_at,topic,output FROM stability_runs ORDER BY id DESC LIMIT ?', (max(1,min(limit,100)),)).fetchall()
    return [{'id':r['id'],'created_at':r['created_at'],'topic':r['topic'],'output':json.loads(r['output'])} for r in rows]

@app.post('/api/stability/run')
async def stability_run(body:dict[str,Any]):
    topic=(body.get('topic') or '').strip()
    if len(topic)<5: raise HTTPException(400,'Provide a scenario or claim of at least 5 characters.')
    conditions=[
      {'name':'Baseline','description':'Original claim and available information','perturbation':'No changes'},
      {'name':'Minor wording change','description':'Equivalent paraphrase request; meaning should remain unchanged','perturbation':'Surface wording varied'},
      {'name':'Critical evidence missing','description':'Answer with explicit uncertainty because no additional evidence is provided','perturbation':'Evidence availability constrained'},
      {'name':'Contradictory evidence introduced','description':'A hypothetical contrary premise is added, clearly not presented as factual evidence','perturbation':'Synthetic contradiction introduced'}
    ]
    prompts=[
      f"Evaluate and answer this scenario directly: {topic}",
      f"Provide the same evaluation and answer, but treat this as an equivalent rephrasing request. Preserve the meaning of the scenario: {topic}",
      f"Evaluate this scenario while explicitly assuming critical supporting information is unavailable. Do not invent facts or sources. Clearly express uncertainty if the scenario cannot be concluded from the information given: {topic}",
      f"Evaluate this scenario after adding a hypothetical contrary premise: 'Assume there is credible evidence that challenges the original claim.' This opposing premise is synthetic for this experiment, not a real-world source. Explain whether it would warrant a changed conclusion: {topic}"
    ]
    labels=['Baseline','Minor wording change','Critical evidence missing','Contradictory evidence introduced']
    try:
        responses=await asyncio.gather(*[llm([{'role':'system','content':'You are answering a controlled research sensitivity condition. Be concise. Do not claim external verification. Clearly label assumptions and missing information.'},{'role':'user','content':prompt}],max_tokens=700) for prompt in prompts])
    except HTTPException as exc:
        raise exc
    result_rows=[{'condition':labels[i],'description':conditions[i]['description'],'perturbation':conditions[i]['perturbation'],'answer':responses[i]} for i in range(4)]
    # Approximate surface-level output similarity is intentionally not presented as correctness or calibrated stability.
    def normalized(text):
        return re.findall(r'[\w]+',text.lower(),flags=re.UNICODE)
    token_a=set(normalized(responses[0]));token_b=set(normalized(responses[1]))
    similarity=round(100*len(token_a&token_b)/max(1,len(token_a|token_b)),1)
    payload={'topic':topic,'protocol':'SENSITIVITY PROTOCOL v1','label':'LIVE MODEL RESPONSES — synthetic perturbations; not accuracy measurements','conditions':result_rows,'metrics':{'baseline_paraphrase_token_jaccard_percent':similarity,'meaning':'Surface lexical overlap only. This is not semantic decision stability or correctness.'},'warning':'The missing-evidence and contrary-premise conditions are experimental prompts, not real-world evidence. Four model responses were generated; no truth labels or accuracy scoring are included.'}
    with db() as con:
        con.execute('INSERT INTO stability_runs(created_at,topic,output) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),topic,json.dumps(payload,ensure_ascii=False)))
    return payload
