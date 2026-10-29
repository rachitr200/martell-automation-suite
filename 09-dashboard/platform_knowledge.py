"""Document ingestion and hybrid retrieval with optional hosted embeddings."""
import hashlib
import math
import os
import re
from collections import Counter
import httpx
from fastapi import HTTPException
from sqlalchemy import select, text
from platform_models import KnowledgeChunk


def terms(value):
    return re.findall(r'[a-z0-9]{3,}',value.lower())


def embed(texts):
    key = os.getenv('OPENAI_API_KEY','')
    model = os.getenv('EMBEDDING_MODEL','text-embedding-3-small')
    if not key:
        raise HTTPException(503,'Configure OPENAI_API_KEY for embeddings, or use lexical retrieval.')
    response = httpx.post('https://api.openai.com/v1/embeddings',headers={'Authorization':'Bearer '+key},json={'model':model,'input':texts,'dimensions':1536},timeout=30)
    if response.is_error:
        raise HTTPException(502,f'Embedding provider returned HTTP {response.status_code}.')
    return [r['embedding'] for r in sorted(response.json()['data'],key=lambda r:r['index'])], model


def ingest(sessions, title, content, semantic=False):
    blocks = [content[i:i+1000] for i in range(0,len(content),850)]
    vectors, model = embed(blocks) if semantic else ([None]*len(blocks),None)
    with sessions() as s:
        for i,(block,vector) in enumerate(zip(blocks,vectors)):
            key = hashlib.sha256((title+'\n'+str(i)+'\n'+block).encode()).hexdigest()[:32]
            s.merge(KnowledgeChunk(id=key,title=title,text=block,embedding=vector,embedding_model=model))
        s.commit()
        # pgvector is optional and explicitly provisioned by the deployment's DB owner.
        if semantic and s.bind.dialect.name == 'postgresql' and os.getenv('PGVECTOR_ENABLED') == '1':
            for row in s.scalars(select(KnowledgeChunk).where(KnowledgeChunk.title==title)).all():
                if row.embedding:
                    s.execute(text('INSERT INTO platform_vectors (chunk_id, embedding, embedding_model) VALUES (:id, CAST(:v AS vector), :model) ON CONFLICT (chunk_id) DO UPDATE SET embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model'),{'id':row.id,'v':str(row.embedding),'model':row.embedding_model})
            s.commit()
    return {'chunks':len(blocks),'mode':'hybrid' if semantic else 'lexical','embedding_model':model}


def search(sessions, query, semantic=False):
    with sessions() as s:
        rows = s.scalars(select(KnowledgeChunk).limit(1000)).all()
        q = Counter(terms(query))
        scored = {r.id:sum(min(n,Counter(terms(r.text))[t]) for t,n in q.items())/max(1,len(q)) for r in rows}
        if semantic:
            vectors, model = embed([query])
            v = vectors[0]
            if s.bind.dialect.name == 'postgresql' and os.getenv('PGVECTOR_ENABLED') == '1':
                nearest = s.execute(text('SELECT chunk_id, 1 - (embedding <=> CAST(:v AS vector)) AS score FROM platform_vectors WHERE embedding_model = :model ORDER BY embedding <=> CAST(:v AS vector) LIMIT 10'),{'v':str(v),'model':model}).all()
                semantic_scores = {r[0]:float(r[1]) for r in nearest}
            else:
                def cosine(a,b):
                    return sum(x*y for x,y in zip(a,b))/max(1e-12,math.sqrt(sum(x*x for x in a)*sum(x*x for x in b)))
                semantic_scores = {r.id:cosine(v,r.embedding) for r in rows if r.embedding and r.embedding_model==model and len(r.embedding)==len(v)}
            scored = {r.id:.4*scored[r.id]+.6*semantic_scores.get(r.id,0) for r in rows}
        results = sorted(rows,key=lambda r:scored[r.id],reverse=True)
        return [{'id':r.id,'title':r.title,'text':r.text,'score':round(scored[r.id],4)} for r in results if scored[r.id]>0][:4]
