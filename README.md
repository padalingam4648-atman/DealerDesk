Track: aiml

# VIKMO DealerDesk — Dealership Management & Intelligence Platform

## Overview
VIKMO DealerDesk is an automotive dealership operations platform integrating a high-performance backend, an AI-powered conversational parts assistant, and statistical demand forecasting for motorcycle spare parts. Built for authorized multi-brand dealerships, it powers live inventory tracking, draft procurement orders, catalogue search, and automated replenishment.

---

## Track & Scope of Implementation

### Completed Tracks & Components
- **Part A1 — Backend Core**: PostgreSQL models, migrations, REST API endpoints for spare parts catalogue, live warehouse inventory, dealership management, and DRAFT purchase order creation (`catalog`, `dealers`, `orders`, `core`).
- **Part C — Dealer Assistant (GenAI)**: Conversational parts and replenishment assistant with function calling, BM25 retrieval, real-time database grounding, prompt injection defenses, and draft order creation (`assistant`).
- **Part D — Demand Forecasting & Reorder Suggestions (ML)**: Statistical multi-horizon demand forecasting pipeline, temporal rolling-origin backtesting, and live safety stock / reorder calculation endpoints (`ml`, `forecasts`).

### Unattempted Tracks (As Permitted for AI/ML Track)
- **Part A2 — Full Order Engine**: Confirmed/dispatched transitions, credit limit checks, and concurrency locks were not implemented beyond DRAFT orders.
- **Part B — Supplier Sync Feed**: The mock supplier sync client and feed reconciliation were not attempted.
- **Part E — Frontend Web Application**: No frontend dashboard was attempted; all functionality is exposed via clean REST APIs.

---

## Tech Stack
- **Backend Core**: Python 3.12, Django 4.2+, Django REST Framework, PostgreSQL (`psycopg[binary]`, `dj-database-url`).
- **GenAI / Assistant**: Groq Python SDK (`groq`), native function calling, BM25 text retrieval, token normalization.
- **Forecasting & ML Pipeline**: LightGBM, scikit-learn, pandas, numpy (isolated in `ml/requirements-ml.txt`).
- **DevOps & Verification**: Docker (PostgreSQL container), standard library unittest, custom contract smoke tester.

---

## Setup Instructions

### 1. Prerequisites
- Python 3.11 or newer
- PostgreSQL running locally or hosted (e.g. Neon/Supabase)

### 2. Environment Setup
```bash
# Create and activate a virtual environment
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Install core runtime dependencies (lightweight, cross-platform)
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```
Key environment variables:
- `DATABASE_URL`: PostgreSQL connection URL (e.g., `postgres://postgres:postgres@localhost:5432/dealerdesk`)
- `SUPPLIER_API_URL`: Supplier mock endpoint (e.g., `http://127.0.0.1:8099`)
- `SUPPLIER_API_KEY`: Supplier API authentication key
- `GROQ_API_KEY`: Your Groq Cloud API key (required for Phase 3 Assistant)
- `ASSISTANT_MODEL`: Optional model override (defaults to `openai/gpt-oss-120b`, fallback `llama-3.3-70b-versatile`)

---

## Running the Application

Execute the standard sequence required by the grading runner:
```bash
# 1. Apply database migrations
python manage.py migrate --noinput

# 2. Seed data (idempotent, safe to run twice)
python manage.py seed_data
python manage.py seed_data

# 3. Start development server
python manage.py runserver 0.0.0.0:8000 --noreload
```

---

## Testing & Verification

### Run Django Unit Test Suite
```bash
python manage.py test
```
*Executes all 30 test cases across Core, Forecasts, and Assistant in ~10 seconds.*

### Run Official Smoke Test
```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
```
*Verifies all 10 checks across Core endpoints, Assistant contract response, and Forecasting CSV / APIs.*

---

## LLM Provider & Architecture

- **Provider**: **Groq Cloud**
- **Default Model**: `openai/gpt-oss-120b` (specified in `dealerdesk/settings.py:101`)
- **Fallback Models**: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`
- **Retrieval Engine**: Pure Python in-memory BM25 index with token normalization (splitting model codes like `Duke390` $\rightarrow$ `duke 390`), automotive synonym mapping, and vehicle fitment scoring (+15 for direct match, +4 for universal, -50 for conflicting vehicles). Zero cold-start latency (< 3 ms index build).
- **Grounding Verifier**: Verifies all cited SKUs against the database; enforces live tool execution during the turn; corrects or removes ungrounded prices and stocks.
- **Safety**: Regex heuristic detector withholds planted prompt injections (`[description withheld: contains instructions]`). System prompt instructs LLM that catalogue data is untrusted.

---

## Demand Forecasting Pipeline (`ml/`)

### Regenerate Production Forecast
ML dependencies are isolated to keep the primary Django server installation fast and lean:
```bash
pip install -r ml/requirements-ml.txt
python ml/train_forecast.py
```
Outputs `ml/forecast.csv` (exactly 160 rows, 40 SKUs $\times$ 4 weeks: `2026-09-28` to `2026-10-19`).

### Backtest Benchmark Results (5 Rolling Origins)
- **Baseline 1 (Last Value)**: WAPE = 34.14%, MAE = 12.02
- **Baseline 2 (Recent Average)**: WAPE = 28.57%, MAE = 10.05
- **Baseline 3 (Same Week Last Year)**: WAPE = 32.00%, MAE = 11.26
- **DealerDesk Model (Ours)**: **WAPE = 22.06%, MAE = 7.76**
- **Improvement**: 22.8% relative error reduction over the best baseline.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/` | Service health status |
| `GET` | `/api/products/` | Paginated product catalogue |
| `GET` | `/api/products/{sku}/` | Single product details |
| `PUT` | `/api/inventory/{sku}/` | Update physical stock for a product |
| `GET` | `/api/dealers/` | Paginated list of dealerships |
| `POST` | `/api/dealers/` | Register new dealership |
| `POST` | `/api/orders/` | Create a DRAFT purchase order |
| `GET` | `/api/orders/{order_number}/` | Retrieve purchase order by number |
| `GET` | `/api/orders/` | List orders (filterable by dealer/status) |
| `POST` | `/api/assistant/chat/` | Conversational Dealer Assistant with tool calling |
| `GET` | `/api/forecast/{sku}/` | 4-week demand forecast for a SKU |
| `GET` | `/api/reorder-suggestions/` | Live replenishment suggestions for 40 SKUs |

---

## Project Structure
```
DealerDesk/
├── catalog/               # Products and Inventory models, views, serializers
├── dealers/               # Dealership profiles and credit allocation
├── orders/                # DRAFT order management and financial arithmetic
├── forecasts/             # Forecast read API and live reorder suggestions engine
├── assistant/             # GenAI Assistant: tools, BM25 retrieval, grounding, agent loop
├── core/                  # Health endpoint and idempotent seed_data management command
├── common/                # Custom exception handler, money formatters, pagination
├── dealerdesk/            # Project configuration, root settings, URL configuration
├── ml/                    # Forecasting features, backtesting, and training pipeline
│   ├── features.py        # Vectorized lag/festive feature engineering
│   ├── evaluate.py        # Rolling-origin backtester and baseline evaluations
│   ├── train_forecast.py  # Production forecast generator
│   ├── requirements-ml.txt# Heavy ML dependencies (lightgbm, scikit-learn, pandas)
│   └── forecast.csv       # Production 160-row forecast table
├── data/                  # Original catalogue, sales, and calendar CSVs (unmodified)
├── docs/                  # Architectural notes and decisions
│   ├── phase1_notes.md    # Phase 1 backend architecture
│   ├── phase2_notes.md    # Phase 2 ML models & backtest analysis
│   ├── phase3_notes.md    # Phase 3 Assistant architecture & safety
│   └── video_script.md    # Timed 5-minute video walkthrough script
├── scripts/
│   └── chat_demo.py       # Live LLM conversation scenario demonstration script
├── DECISIONS.md           # Answers to the 8 required architectural questions
├── manage.py              # Django management CLI
├── requirements.txt       # Lean root dependencies
└── smoke_test.py          # Grader smoke test script
```

---

## Assumptions & Limitations
1. **Retrieval**: Uses in-memory BM25 with synonym expansion rather than semantic vector embeddings. Highly resilient and zero-latency (< 3 ms), but sensitive to severe misspellings outside covered synonyms.
2. **Safety Defense**: Prompt injection detection uses heuristic pattern matching. Sophisticated multi-lingual or obfuscated jailbreaks could bypass regex detectors without model-level guardrails.
3. **Forecasting**: Intermittent demand for rare SKUs uses Syntetos-Boylan Approximation (SBA), yielding a constant weekly rate that exhibits high WAPE during zero-sales weeks despite capturing aggregated demand.

---

## Video Walkthrough
Video: `<VIDEO_LINK>`
*(See [docs/video_script.md](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/docs/video_script.md) for the timed 5-minute spoken walkthrough script).*
