-- Optional database-owner setup before PGVECTOR_ENABLED=1.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS platform_vectors (
 chunk_id varchar(64) PRIMARY KEY,
 embedding vector(1536) NOT NULL,
 embedding_model text NOT NULL
);
CREATE INDEX IF NOT EXISTS platform_vectors_cosine ON platform_vectors USING hnsw (embedding vector_cosine_ops);
