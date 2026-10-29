"""Authenticated API for copilot runs, approvals, telemetry, RAG and connectors."""
import asyncio
import hashlib
import json
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from platform_models import AuditEntry, ConnectorReceipt, CopilotRun, EvalResult, KnowledgeChunk, UserSession
from platform_security import COOKIE, bearer, configured, login, require_role, role_for
from platform_copilot import Workflow
from platform_knowledge import ingest, search
from platform_connectors import hubspot_check, notify, stripe_get


class Credentials(BaseModel):
    username: str = Field(min_length=1,max_length=150)
    password: str = Field(min_length=1,max_length=256)


class Question(BaseModel):
    question: str = Field(min_length=3,max_length=2000)
    customer_id: str = Field(min_length=1,max_length=100)
    mode: str = Field(default='offline',pattern='^(offline|claude)$')


class Decision(BaseModel):
    approved: bool
    reason: str = Field(min_length=3,max_length=500)


class Document(BaseModel):
    title: str = Field(min_length=1,max_length=150)
    content: str = Field(min_length=10,max_length=50000)
    semantic: bool = False


class Search(BaseModel):
    query: str = Field(min_length=1,max_length=500)
    semantic: bool = False


class ConnectorAction(BaseModel):
    customer_id: str = Field(min_length=1,max_length=100)


class AutomationText(BaseModel):
    text: str = Field(min_length=1,max_length=4000)


def install_platform(app,sessions,engine,data_dir,lock,snapshot,retry):
    router=APIRouter(prefix='/api/platform')
    attempts=defaultdict(deque)
    workflow=None

    def audit(actor,action,target,detail=None):
        with sessions() as s:
            s.add(AuditEntry(id=uuid.uuid4().hex,actor=actor,action=action,target=target,detail=detail or {}));s.commit()

    def serial(run):
        return {'id':run.id,'actor':run.actor,'mode':run.mode,'status':run.status,'question':run.question,
                'customer_id':run.customer_id,'result':run.result,'trace':run.trace,'input_tokens':run.input_tokens,
                'output_tokens':run.output_tokens,'duration_ms':round(run.duration_ms,1),'created_at':run.created_at.isoformat()}

    def persist(run_id,result,elapsed):
        with sessions() as s:
            run=s.get(CopilotRun,run_id);run.result={**result.get('result',{}),'execution':result.get('execution')}
            run.trace=result.get('trace',[]);usage=result.get('usage',{})
            run.input_tokens=usage.get('input_tokens',0);run.output_tokens=usage.get('output_tokens',0)
            run.duration_ms+=elapsed
            run.status='awaiting_approval' if result.get('__interrupt__') else 'rejected' if result.get('execution',{}).get('status')=='rejected' else 'completed'
            s.commit()
            return serial(run)

    def start_run(body,identity,proposal=None):
        if not any(c['id']==body.customer_id for c in snapshot()['customers']) and not any(e['customer_id']==body.customer_id for e in snapshot()['events']):
            raise HTTPException(404,'Customer not found')
        with lock:
            with sessions() as s:
                if body.mode=='claude':
                    count=s.scalar(select(func.count()).select_from(CopilotRun).where(CopilotRun.mode=='claude',CopilotRun.created_at>=datetime.now(timezone.utc)-timedelta(days=1)))
                    if count>=int(os.getenv('MAX_LIVE_RUNS_PER_DAY','20')):
                        raise HTTPException(429,'Daily live-run limit reached')
                run_id=uuid.uuid4().hex
                s.add(CopilotRun(id=run_id,actor=identity['actor'],mode=body.mode,question=body.question,customer_id=body.customer_id))
                s.commit()
            start=time.monotonic()
            try:
                out=workflow.start(run_id,body.question,body.customer_id,body.mode,proposal)
                result=persist(run_id,out,(time.monotonic()-start)*1000)
                audit(identity['actor'],'investigate',run_id,{'mode':body.mode,'status':result['status']})
                # Explicit opt-in; metadata only, never raw customer records or model prompts.
                if os.getenv('LANGSMITH_TRACING')=='true' and os.getenv('LANGSMITH_API_KEY'):
                    try:
                        from langsmith import Client
                        Client().create_run(name='operations-copilot',run_type='chain',inputs={'run_id':run_id,'mode':body.mode},outputs={'status':result['status'],'input_tokens':result['input_tokens'],'output_tokens':result['output_tokens']},project_name=os.getenv('LANGSMITH_PROJECT','martell-operations'))
                    except Exception:
                        audit('system','trace_export_failed',run_id)
                return result
            except Exception as exc:
                with sessions() as s:
                    run=s.get(CopilotRun,run_id);run.status='failed';run.duration_ms=(time.monotonic()-start)*1000
                    run.result={'error':exc.detail if isinstance(exc,HTTPException) else 'Investigation failed validation or reached a provider limit. No action was executed.'};s.commit()
                if isinstance(exc,HTTPException):raise
                raise HTTPException(502,'Investigation failed validation or provider request; no action executed.') from exc

    @router.get('/status')
    def status(request:Request):
        return {'identity':role_for(request,sessions),'auth_configured':configured(),
                'database':engine.dialect.name,'durable_database_configured':engine.dialect.name=='postgresql',
                'copilot_ready':bool(os.getenv('ANTHROPIC_API_KEY') and os.getenv('ANTHROPIC_MODEL')),
                'model':os.getenv('ANTHROPIC_MODEL','not configured'),
                'embeddings_ready':bool(os.getenv('OPENAI_API_KEY')),
                'pgvector_enabled':os.getenv('PGVECTOR_ENABLED')=='1',
                'langsmith_enabled':os.getenv('LANGSMITH_TRACING')=='true' and bool(os.getenv('LANGSMITH_API_KEY')),
                'stripe_test_ready':os.getenv('STRIPE_TEST_SECRET_KEY','').startswith('sk_test_'),
                'hubspot_test_ready':bool(os.getenv('HUBSPOT_TEST_TOKEN')) and os.getenv('HUBSPOT_TEST_ACCOUNT')=='1',
                'slack_test_ready':bool(os.getenv('SLACK_TEST_WEBHOOK_URL')),
                'external_writes_enabled':os.getenv('ALLOW_EXTERNAL_WRITES')=='1',
                'mcp_ready':bool(os.getenv('MCP_READ_TOKEN')),'automation_ready':bool(os.getenv('AUTOMATION_TOKEN')),
                'recovery_worker_enabled':os.getenv('RECOVERY_WORKER_ENABLED')=='1',
                'max_live_runs_per_day':int(os.getenv('MAX_LIVE_RUNS_PER_DAY','20'))}

    @router.post('/login')
    def sign_in(body:Credentials,request:Request,response:Response):
        key=request.client.host if request.client else 'unknown';now=time.time()
        if len(attempts)>1000:attempts.clear()
        q=attempts[key]
        while q and q[0]<now-300:q.popleft()
        if len(q)>=5:raise HTTPException(429,'Too many login attempts. Try again in five minutes.')
        q.append(now)
        token,identity=login(body.username,body.password,sessions)
        response.set_cookie(COOKIE,token,max_age=8*3600,httponly=True,secure=request.url.scheme=='https',samesite='strict',path='/')
        audit(identity['actor'],'login','session');return identity

    @router.post('/logout')
    def sign_out(request:Request,response:Response):
        token=request.cookies.get(COOKIE,'')
        with sessions() as s:
            s.execute(delete(UserSession).where(UserSession.token_hash==hashlib.sha256(token.encode()).hexdigest()));s.commit()
        response.delete_cookie(COOKIE,path='/');return {'status':'signed_out'}

    @router.get('/runs')
    def runs(request:Request):
        require_role(request,sessions)
        with sessions() as s:return [serial(r) for r in s.scalars(select(CopilotRun).order_by(CopilotRun.created_at.desc()).limit(100)).all()]

    @router.post('/investigate')
    def investigate(body:Question,request:Request):
        return start_run(body,require_role(request,sessions))

    @router.post('/hubspot-proposal')
    def hubspot_proposal(body:ConnectorAction,request:Request):
        identity=require_role(request,sessions)
        return start_run(Question(question='Preview and approve a HubSpot test-account sync',customer_id=body.customer_id),identity,{'kind':'hubspot_sync'})

    @router.post('/runs/{run_id}/decision')
    def decision(run_id:str,body:Decision,request:Request):
        identity=require_role(request,sessions,('admin',))
        with lock:
            with sessions() as s:
                run=s.get(CopilotRun,run_id)
                if not run:raise HTTPException(404,'Run not found')
                if run.status!='awaiting_approval':raise HTTPException(409,'This run is not awaiting approval')
                run.status='resuming';s.commit()
            audit(identity['actor'],'approve' if body.approved else 'reject',run_id,{'reason':body.reason})
            start=time.monotonic()
            try:
                return persist(run_id,workflow.resume(run_id,body.approved),(time.monotonic()-start)*1000)
            except Exception as exc:
                with sessions() as s:
                    run=s.get(CopilotRun,run_id);run.status='failed';run.result={**run.result,'execution':{'status':'failed','error':'Action failed; inspect configuration and event state before proposing another run.'}};s.commit()
                if isinstance(exc,HTTPException):raise
                raise HTTPException(502,'Approved action failed. It was not marked successful.') from exc

    @router.get('/audit')
    def audit_log(request:Request):
        require_role(request,sessions,('admin',))
        with sessions() as s:return [{'id':r.id,'actor':r.actor,'action':r.action,'target':r.target,'detail':r.detail,'created_at':r.created_at.isoformat()} for r in s.scalars(select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(100)).all()]

    @router.get('/metrics')
    def metrics(request:Request):
        require_role(request,sessions)
        with sessions() as s:
            rows=s.scalars(select(CopilotRun).order_by(CopilotRun.created_at.desc()).limit(1000)).all()
            inputs=sum(r.input_tokens for r in rows);outputs=sum(r.output_tokens for r in rows)
            prices=(os.getenv('INPUT_PRICE_PER_MILLION'),os.getenv('OUTPUT_PRICE_PER_MILLION'))
            cost=(inputs*float(prices[0])+outputs*float(prices[1]))/1e6 if all(prices) else None
            durations=sorted(r.duration_ms for r in rows)
            return {'runs':len(rows),'completed':sum(r.status=='completed' for r in rows),'failed':sum(r.status=='failed' for r in rows),
                    'awaiting_approval':sum(r.status=='awaiting_approval' for r in rows),'input_tokens':inputs,'output_tokens':outputs,
                    'p95_duration_ms':durations[min(len(durations)-1,int(len(durations)*.95))] if durations else 0,
                    'estimated_cost_usd':cost,'cost_note':'Estimate uses operator-configured model rates; not a provider invoice.' if cost is not None else 'Set model rates to enable estimates; token usage is still measured.'}

    @router.get('/outcomes')
    def outcomes(request:Request):
        require_role(request,sessions)
        from platform_outcomes import summarize_outcomes
        with sessions() as s:
            rows=s.scalars(select(CopilotRun).order_by(CopilotRun.created_at.desc()).limit(1000)).all()
            return summarize_outcomes(rows,os.getenv('MANUAL_RECOVERY_MINUTES'))

    @router.post('/evaluate-copilot')
    def evaluate_copilot(request:Request):
        who=require_role(request,sessions)
        from platform_evaluation import evaluate_workflow
        report=evaluate_workflow()
        with sessions() as s:
            s.add(EvalResult(id=uuid.uuid4().hex,report=report));s.commit()
        audit(who['actor'],'evaluate','copilot',{'passed':report['passed'],'total':report['total']})
        return report

    @router.get('/documents')
    def documents(request:Request):
        require_role(request,sessions)
        with sessions() as s:
            rows=s.execute(select(KnowledgeChunk.title,func.count()).group_by(KnowledgeChunk.title)).all()
            return [{'title':r[0],'chunks':r[1]} for r in rows]

    @router.post('/documents')
    def add_document(body:Document,request:Request):
        who=require_role(request,sessions,('admin',))
        with sessions() as s:
            if s.scalar(select(func.count()).select_from(KnowledgeChunk))>=500:
                raise HTTPException(409,'Knowledge limit reached; remove obsolete documents before uploading more.')
        out=ingest(sessions,body.title,body.content,body.semantic);audit(who['actor'],'ingest_document',body.title,{'chunks':out['chunks']});return out

    @router.post('/search')
    def search_documents(body:Search,request:Request):
        require_role(request,sessions)
        return {'results':search(sessions,body.query,body.semantic),'mode':'hybrid' if body.semantic else 'lexical'}

    @router.post('/evaluate')
    def evaluate(request:Request):
        who=require_role(request,sessions)
        # Offline classifier fixtures; copilot regressions have their own endpoint.
        from batch_classifier.baseline import classify_text
        cases=json.loads((Path(__file__).parent/'evals/operations.json').read_text())
        results=[]
        for case in cases:
            actual=classify_text(case['text']);results.append({'id':case['id'],'expected':case['label'],'actual':actual,'passed':actual==case['label']})
        report={'kind':'offline_classifier_regression','passed':sum(r['passed'] for r in results),'total':len(results),'cases':results,'live_model_evaluated':False}
        with sessions() as s:s.add(EvalResult(id=uuid.uuid4().hex,report=report));s.commit()
        audit(who['actor'],'evaluate','classifier',{'passed':report['passed'],'total':report['total']});return report

    @router.get('/connector-check/{name}')
    def check_connector(name:str,request:Request):
        require_role(request,sessions,('admin',))
        if name=='stripe':
            data=stripe_get('events?limit=1')
            return {'connected':True,'test_mode':True,'sample_events':len(data.get('data',[]))}
        if name=='hubspot':return hubspot_check()
        raise HTTPException(404,'Unknown connector')

    @router.post('/slack-preview')
    def slack_preview(body:AutomationText,request:Request):
        require_role(request,sessions)
        return notify(body.text,dry_run=True)

    app.include_router(router)

    @app.post('/api/automation/classify')
    def automation(body:AutomationText,request:Request):
        if not bearer(request,'AUTOMATION_TOKEN'):raise HTTPException(401,'Invalid automation token')
        from batch_classifier.baseline import classify_text
        result={'label':classify_text(body.text),'requires_review':True,'mode':'keyword_baseline'}
        audit('n8n','classify','automation',{'label':result['label']});return result

    @app.post('/api/connectors/stripe/webhook')
    async def stripe_webhook(request:Request):
        from app.stripe_verify import SignatureError, verify_signature
        secret=os.getenv('STRIPE_TEST_WEBHOOK_SECRET','')
        if not secret:raise HTTPException(503,'Test webhook secret not configured')
        payload=await request.body()
        if len(payload)>256000:raise HTTPException(413,'Payload too large')
        try:verify_signature(payload,request.headers.get('stripe-signature',''),secret,300)
        except SignatureError as exc:raise HTTPException(400,'Invalid webhook signature') from exc
        try:data=json.loads(payload);event_id=data['id'];kind=data['type']
        except (ValueError,KeyError,TypeError) as exc:raise HTTPException(400,'Malformed event') from exc
        if data.get('livemode') is not False:raise HTTPException(409,'Only test-mode Stripe events are accepted')
        with lock,sessions() as s:
            if s.get(ConnectorReceipt,event_id):return {'status':'duplicate'}
            s.add(ConnectorReceipt(id=event_id,source='stripe_test',kind=kind,summary={'livemode':False,'received':True}));s.commit()
        return {'status':'recorded_test_event','note':'Stored in the sandbox inbox; no customer entitlement was changed.'}

    @router.get('/connector-events')
    def connector_events(request:Request):
        require_role(request,sessions)
        with sessions() as s:return [{'id':r.id,'source':r.source,'kind':r.kind,'summary':r.summary} for r in s.scalars(select(ConnectorReceipt).order_by(ConnectorReceipt.created_at.desc()).limit(50)).all()]

    # Token-scoped, read-only MCP transport. No write/approval tools exposed.
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    hostname=os.getenv('RENDER_EXTERNAL_HOSTNAME','')
    hosts=['localhost:*','127.0.0.1:*','testserver']+([hostname] if hostname else [])
    origins=['http://localhost:*','http://127.0.0.1:*']+(['https://'+hostname] if hostname else [])
    mcp=FastMCP('Martell Operations',stateless_http=True,json_response=True,streamable_http_path='/',transport_security=TransportSecuritySettings(allowed_hosts=hosts,allowed_origins=origins))

    @mcp.tool()
    def get_customer(customer_id:str)->dict:
        """Read synthetic customer status and at most 20 recorded lifecycle events."""
        return workflow.tool('get_customer',{'customer_id':customer_id},customer_id)

    @mcp.tool()
    def list_failed_events(customer_id:str)->list:
        """Read failed or received events for a selected customer. Does not retry."""
        return workflow.tool('list_failed_events',{'customer_id':customer_id},customer_id)

    @mcp.tool()
    def search_operations_knowledge(query:str)->list:
        """Search administrator-approved operational notes. Read-only lexical search."""
        return search(sessions,query[:500])

    app.mount('/mcp',mcp.streamable_http_app())

    @asynccontextmanager
    async def lifecycle():
        nonlocal workflow
        workflow=Workflow(sessions,engine,data_dir,snapshot,retry)
        # Seed documents only once. Uploaded content remains after restarts.
        with sessions() as s:empty=s.scalar(select(func.count()).select_from(KnowledgeChunk))==0
        if empty:
            for path in (Path(__file__).parent/'knowledge').glob('*.md'):
                ingest(sessions,path.stem,path.read_text())
        async def recovery_loop():
            from platform_worker import tick
            while True:
                try:
                    await asyncio.to_thread(tick,sessions,lock,retry)
                except Exception:
                    audit('system','recovery_tick_failed','worker')
                await asyncio.sleep(2)
        task=asyncio.create_task(recovery_loop()) if os.getenv('RECOVERY_WORKER_ENABLED')=='1' else None
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            if task:
                task.cancel()
                try:await task
                except asyncio.CancelledError:pass
            workflow.close()

    return lifecycle

