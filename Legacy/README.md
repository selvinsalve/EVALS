# AI Order Assistant

A production-style, enterprise-grade AI customer support and order assistant application built from scratch. It features a modern **Streamlit Web UI**, a **FastAPI backend**, an **Order API service** backed by SQLite and SQLAlchemy ORM, a **modular RAG system** powered by ChromaDB, and an **orchestration layer** supporting both **OpenAI** and an offline, deterministic **DEMO mode** (no API key required).

---

## Architecture Overview

```
                          User
                            │
                            ▼
                    Streamlit Web UI
                            │
                            ▼
              AI Assistant Orchestration Layer
                            │
                   Intent / Requirement Router
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
   Need Order API?                         Need RAG?
         │                                     │
         ▼                                     ▼
     Order API                            RAG System
(SQLite + SQLAlchemy)                 (ChromaDB Vectors)
         │                                     │
         ▼                                     ▼
  Live Order Telemetry                  Policies & FAQs
         │                                     │
         └──────────────────┬──────────────────┘
                            ▼
                     Context Builder
                            │
                            ▼
                     LLM Reasoning
                (OpenAI / Demo Mode)
                            │
                            ▼
                      Final Response
           (Answer + Badges + Order Card + Sources)
```

---

## Features

- **Strict Grounding Rules**: Never fabricates order statuses, tracking numbers, or delivery dates.
- **Intelligent Routing**: Determines whether a question requires live Order API data, RAG policy retrieval, both, or neither.
- **Order Action APIs**: Real cancellation workflow that validates order state before updating the database.
- **Conversation Memory**: Remembers referenced Order IDs across multi-turn dialogues.
- **Zero-Key DEMO Mode**: Runs entirely locally out of the box with zero external dependencies.
- **Rich Streamlit UI**: Interactive order cards, source citation accordions, system badges (`Order API ✓`, `RAG ✓`), and observability metrics.
- **Enterprise Code Quality**: Type hints, Pydantic v2 schemas, structured logging, service-repository decoupling, and a full pytest suite.

---

## Project Structure

```
ai-order-assistant/
├── README.md                   # Complete architectural & operational guide
├── requirements.txt            # Python dependencies
├── .env.example                # Configuration template
├── .env                        # Local active configuration
├── .gitignore                  # Git ignore rules
├── Dockerfile                  # Multi-service production container
├── docker-compose.yml          # Docker Compose orchestration
├── entrypoint.sh               # Container startup script
│
├── app/
│   ├── __init__.py
│   ├── config.py               # Pydantic BaseSettings configuration
│   ├── main.py                 # FastAPI application, lifespan, middleware
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py         # SQLAlchemy engine, session maker, get_db
│   │   ├── models.py           # Customer, Order, OrderItem, Shipment models
│   │   └── seed.py             # Database creation and 10 customers / 25 orders
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py           # GET /health
│   │   ├── orders.py           # Order API routes (/orders, /customers, /cancel)
│   │   └── assistant.py        # POST /assistant/chat endpoint
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── order_service.py    # Order query and cancellation business logic
│   │   ├── rag_service.py      # High-level RAG query service
│   │   ├── llm_service.py      # BaseLLMService, OpenAILLMService, DemoLLMService
│   │   └── assistant_service.py# Core orchestration router and response synthesizer
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingest.py           # Ingestion pipeline (.md, .txt, .pdf)
│   │   ├── retriever.py        # Top-k similarity retriever with citations
│   │   └── vector_store.py     # ChromaDB vector store manager
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── order.py            # Pydantic models for orders, items, tracking
│   │   ├── chat.py             # Pydantic models for chat requests and messages
│   │   └── assistant.py        # Pydantic models for intent and assistant responses
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging.py          # Structured logger and event auditing
│
├── streamlit_app/
│   ├── app.py                  # Streamlit chat interface and sidebar
│   ├── components.py           # Presentation components (cards, badges, citations)
│   └── styles.py               # Modern CSS stylesheet
│
├── data/
│   ├── orders.db               # SQLite database file (generated)
│   ├── chroma/                 # ChromaDB persistent vector database (generated)
│   └── documents/              # E-commerce store policy knowledge base
│       ├── refund_policy.md
│       ├── return_policy.md
│       ├── shipping_policy.md
│       ├── cancellation_policy.md
│       ├── damaged_order_policy.md
│       ├── delivery_policy.md
│       ├── payment_faq.md
│       └── general_faq.md
│
├── tests/
│   ├── __init__.py
│   ├── test_orders.py          # Order service & cancellation tests
│   ├── test_rag.py             # Document loading, chunking & retrieval tests
│   ├── test_assistant.py       # Assistant orchestration & routing tests
│   └── test_api.py             # FastAPI HTTP endpoints tests
│
└── scripts/
    ├── init_db.py              # Script: Initialize database tables
    ├── seed_data.py            # Script: Seed sample e-commerce data
    └── ingest_documents.py     # Script: Ingest policies into ChromaDB
```

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Environment Setup

```bash
# Clone or navigate to the repository
cd ai-order-assistant

# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# Linux / macOS:
source .venv/bin/activate
# Windows (cmd):
# .venv\Scripts\activate.bat
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Default settings in `.env`:
```ini
LLM_PROVIDER=demo
DEMO_MODE=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///./data/orders.db
CHROMA_PERSIST_DIRECTORY=./data/chroma
CHROMA_COLLECTION_NAME=ecommerce_policies
BACKEND_URL=http://localhost:8000
LOG_LEVEL=INFO
```

> **Note**: To use OpenAI rather than Demo mode, set:
> ```ini
> LLM_PROVIDER=openai
> DEMO_MODE=false
> OPENAI_API_KEY=sk-...your-key...
> ```

### 4. Initialize Database & Seed Sample Data

```bash
# Initialize SQLite database tables
python scripts/init_db.py

# Seed 10 customers and 25 realistic orders
python scripts/seed_data.py
```

### 5. Ingest Policy Documents into Vector Database

```bash
# Parse policies/FAQs and embed them into ChromaDB
python scripts/ingest_documents.py
```

---

## Running the Application

### Option A: Run Services Locally

Open **Terminal 1** to start the FastAPI backend:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Documentation will be accessible at: [http://localhost:8000/docs](http://localhost:8000/docs)*

Open **Terminal 2** to start the Streamlit UI:
```bash
streamlit run streamlit_app/app.py
```
*Streamlit UI will be accessible at: [http://localhost:8501](http://localhost:8501)*

---

### Option B: Run with Docker Compose

To build and run the entire stack (FastAPI + Streamlit + SQLite + ChromaDB persistence):

```bash
docker-compose up --build
```

Access the services:
- **Streamlit Web UI**: [http://localhost:8501](http://localhost:8501)
- **FastAPI OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Seeded Demo Scenarios

The database is pre-populated with 10 customers (`CUS-001` through `CUS-010`) and 25 orders designed to demonstrate all edge cases:

| Order ID | Customer | Status | Carrier | Description / Test Case |
| :--- | :--- | :--- | :--- | :--- |
| **ORD-1001** | CUS-001 | `SHIPPED` | FedEx | In transit with tracking number `FDX-99482110`. |
| **ORD-1002** | CUS-001 | `DELIVERED` | UPS | Delivered 4 days ago. Eligible for 30-day return. |
| **ORD-1003** | CUS-001 | `PROCESSING` | Pending | **Cancellable**. `cancellation_allowed=True`. |
| **ORD-1004** | CUS-001 | `CANCELLED` | None | Already cancelled and payment refunded. |
| **ORD-1005** | CUS-002 | `DELAYED` | UPS | Delayed in Chicago due to severe weather. |
| **ORD-1006** | CUS-002 | `OUT_FOR_DELIVERY` | USPS | On delivery truck today. |
| **ORD-1007** | CUS-002 | `PLACED` | None | Newly placed. Cancellable & address editable. |
| **ORD-1008** | CUS-003 | `RETURN_REQUESTED`| FedEx | Return inspection pending. |
| **ORD-1009** | CUS-003 | `REFUNDED` | UPS | Returned item with refund processed. |

---

## Example User Flows in Streamlit

Try asking the assistant:

### Flow 1: Order Status (`Order API`)
> **User**: "Where is order ORD-1001?"  
> **Assistant**: Detects `order_status` → Calls Order API → Displays live FedEx tracking status, estimated arrival, items, and structured Order Card.

### Flow 2: Policy Query (`RAG System`)
> **User**: "What is your refund policy?"  
> **Assistant**: Detects `refund` intent → Queries ChromaDB for `refund_policy.md` → Formulates policy summary with expandable citations.

### Flow 3: Delayed Order with Refund Inquiry (`Order API + RAG`)
> **User**: "My order ORD-1001 is delayed. Can I get a refund?"  
> **Assistant**: Queries Order API for `ORD-1001` (status `SHIPPED`) AND retrieves delay transit guarantee policy from RAG → Explains live status, tracking location, and the 14-day lost transit refund threshold without hallucination.

### Flow 4: Order Cancellation (`Order Action API`)
> **User**: "Cancel ORD-1003"  
> **Assistant**: Checks `cancellation_allowed` → Executes cancellation on the database → Confirms 100% refund initiated.  
> **User**: "Cancel ORD-1001"  
> **Assistant**: Checks order status (`SHIPPED`) → Informs user that cancellation cannot be performed once in transit and provides return instructions.

### Flow 5: Customer Latest Order Lookup (`Conversation Context`)
> **User**: "Tell me about my latest order."  
> **Assistant**: Identifies selected demo customer (`CUS-001`) → Fetches the latest placed order (`ORD-1003`) → Summarizes contents and status.

---

## End-to-End Query Lifecycle

```
[User submits query in Streamlit]
       │
       ▼
1. Streamlit client passes query + conversation history to AssistantService
       │
       ▼
2. Intent Detection & Entity Extraction:
   - Identifies intent (e.g. refund_for_delayed_order)
   - Flags needs_order_data (True/False)
   - Flags needs_rag (True/False)
   - Extracts or infers Order ID (e.g. ORD-1001)
       │
       ▼
3. Service Invocation:
   - If needs_order_data: calls OrderService to query SQLite ORM.
     If action is "cancel", executes cancel_order() with atomic DB commit.
   - If needs_rag: calls RAGService to run semantic search in ChromaDB.
       │
       ▼
4. Context Assembly:
   - Compiles live order attributes (or non-existence warning).
   - Compiles retrieved policy excerpts and section headers.
   - Formats recent conversation history.
       │
       ▼
5. Response Synthesis:
   - Sent to LLM (OpenAILLMService or DemoLLMService).
   - Strict Grounding Rules enforce that no tracking numbers or dates are invented.
       │
       ▼
6. Structured Response Return:
   - AssistantResponse schema containing answer, intent, badges, order_data, sources, and latency.
       │
       ▼
7. Streamlit UI Presentation:
   - Renders chat bubble, badges (Order API ✓, RAG ✓), interactive Order Card, and expandable Source Citations.
```

---

## Running the Test Suite

Run all unit and integration tests with `pytest`:

```bash
pytest -v
```

Test coverage includes:
- `test_orders.py`: Order retrieval, not found handling, customer history, cancellation validation.
- `test_rag.py`: File parsing (.md, .txt, .pdf), text chunking, section extraction, ChromaDB similarity retrieval.
- `test_assistant.py`: Intent routing logic, Order API branch, RAG branch, combined delay+refund branch, cancellation actions.
- `test_api.py`: FastAPI endpoints (`/health`, `/orders/{id}`, `/customers/{id}/orders`, `/orders/{id}/cancel`, `/assistant/chat`).

---

## Extensibility

### How to Replace the LLM Provider
1. Inherit from `BaseLLMService` in `app/services/llm_service.py`.
2. Implement `generate()` and `classify_intent()`.
3. Update `get_llm_service()` to instantiate your custom provider (e.g., Anthropic Claude, Azure OpenAI, Ollama, Google Gemini).

### How to Replace ChromaDB
1. Modify `app/rag/vector_store.py`.
2. Implement `add_documents()`, `query()`, and `count()` using your target database (e.g., Qdrant, Pinecone, FAISS, Weaviate, pgvector).
3. The rest of the application interacts exclusively through `VectorStoreManager` and `PolicyRetriever`.

---

## Troubleshooting

1. **Port 8000 or 8501 already in use**:
   - Change `BACKEND_PORT` in `.env` or run:
     `uvicorn app.main:app --port 8001`
     `streamlit run streamlit_app/app.py --server.port 8502`
2. **Missing ChromaDB vector collection**:
   - Run `python scripts/ingest_documents.py` to rebuild the vector index.
3. **Database locked / reset**:
   - Delete `data/orders.db` and re-run:
     `python scripts/init_db.py && python scripts/seed_data.py`
