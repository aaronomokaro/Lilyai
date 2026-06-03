LilyAI
Enterprise document intelligence platform for legal and finance professionals. Find critical insights across large volumes of documents without missing what matters.

"Enterprise-grade document intelligence. Accessible to everyone."


What It Does
LilyAI lets professionals upload large volumes of legal contracts, financial statements, investment memos, and compliance filings and query them in natural language. The system retrieves the most relevant content, surfaces risks proactively, cites every answer back to source documents, and streams results in real time.
Target users: lawyers, paralegals, finance professionals, investment bankers, compliance teams, consultants, and researchers.

Architecture
Retrieval Pipeline
Hybrid RAG combining two retrieval strategies merged via Reciprocal Rank Fusion (RRF):

BM25 lexical search for exact term matching and rare entity retrieval
Voyage-3 semantic embeddings (1024 dimensions) stored in Qdrant Cloud for conceptual similarity

RRF merging produces consistently higher retrieval quality than either strategy alone on legal document queries.
Multi-Agent System
Five agents orchestrated by a central coordinator:
Orchestrator
    Retrieval Agent        - iterative retrieval, up to 3 passes
    Risk Analysis Agent    - 3 parallel sub-agents via asyncio.gather
    Evaluation Agent       - quality control on every response
    Output Generation Agent - professional document formatting
The retrieval agent runs up to 3 passes. After each pass a Haiku evaluator assesses whether retrieved content is sufficient. If not, a query optimiser rewrites the question before the next pass. This directly reduces hallucinations on complex multi-part queries.
Evaluation Framework
Every AI-generated answer is assessed across 7 metrics before delivery:

Faithfulness - is the answer grounded in the retrieved content?
Relevance - does it answer the actual question?
Citation completeness - are all claims cited?
No-answer accuracy - does it correctly decline when content is absent?
Correctness - factual accuracy against source
Completeness - does it cover all relevant content?
Hallucination rate - tracked across model versions for regression testing

Security Model

PostgreSQL Row Level Security across 13 tables with FORCE RLS
Database-level data isolation independent of application-level access controls
Auth0 RS256 JWT with token versioning for immediate session revocation
Idempotency key validation on all write operations
Bandit security scanning on every commit via GitHub Actions

Observability and Resilience

Real-time streaming via WebSocket with Claude API async streaming
Circuit breaker protection on AI calls
Rate limiting via SlowAPI with Redis sliding window
CloudWatch for production monitoring


Tech Stack
LayerTechnologyBackendFastAPI (Python 3.11), Celery, APScheduler, AlembicAIAnthropic Claude API, OpenAI, Voyage-3 embeddingsVector DBQdrant CloudDatabasesPostgreSQL (RLS), RedisDocument ProcessingPyMuPDF, python-docxAuthAuth0, python-joseStorageAWS S3InfrastructureDocker, RailwayCI/CDGitHub Actions (formatting, import sorting, Bandit security scan)ORMSQLAlchemy, Pydantic

System Components

API Gateway (FastAPI) - single entry point, JWT verification, rate limiting
Authentication Service (Auth0) - JWT tokens, token versioning, MFA
Document Service - upload, S3 storage, metadata, lifecycle management
Document Processing Pipeline (Celery) - extract, chunk, embed, index to Qdrant
Query Service - classify, embed, retrieve, generate, stream via WebSocket
Conversation Manager - Redis active context, PostgreSQL archive, rolling summary
Analytics and Usage Service - real-time Redis counters, nightly aggregation
Multi-Agent Orchestrator - coordinator routing to specialist agents
Retrieval Agent - iterative hybrid RAG with evaluator-optimiser loop
Risk Analysis Agent - 3 parallel sub-agents, proactive risk surfacing
Evaluation Agent - 7-metric quality control, async and batch
Output Generation Agent - professional document output, 7 output types
Security Layer - RLS enforcement, audit trail, token revocation
Notification Service - SendGrid system emails
