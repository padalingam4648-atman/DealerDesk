Track: aiml

# VIKMO DealerDesk — Dealership Management & Intelligence Platform

## Overview
VIKMO DealerDesk is an automotive dealership operations platform integrating a high-performance backend, an AI-powered conversational parts assistant, and statistical demand forecasting for motorcycle spare parts. Built for authorized multi-brand dealerships, it powers live inventory tracking, draft procurement orders, catalogue search, and automated replenishment.

---

## Track & Scope of Implementation

### Completed Tracks & Components
- **Part A1 — Backend Core**: PostgreSQL models, migrations, REST API endpoints for spare parts catalogue, live warehouse inventory, dealership management, and DRAFT purchase order creation (`catalog`, `dealers`, `orders`, `core`).
- **Part A2 — Full Order Engine**: Complete order lifecycle state machine (`DRAFT -> CONFIRMED -> DISPATCHED -> DELIVERED` and `DRAFT / CONFIRMED -> CANCELLED`), deterministic row-level locking via `select_for_update` ordered by `product_id` to prevent deadlocks, all-or-nothing stock verification, exact-once stock restoration on cancellation, permanent price lock snapshot on confirmation, sequential daily order numbering (`ORD-YYYYMMDD-NNNN`), and header-based idempotency (`Idempotency-Key`) with unique constraint deduplication (`orders`).
- **Part C — Dealer Assistant (GenAI)**: Conversational parts and replenishment assistant with function calling, BM25 retrieval, real-time database grounding, prompt injection defenses, and draft order creation (`assistant`).
- **Part D — Demand Forecasting & Reorder Suggestions (ML)**: Statistical multi-horizon demand forecasting pipeline, temporal rolling-origin backtesting, and live safety stock / reorder calculation endpoints (`ml`, `forecasts`).
- **Part E — Frontend Web Application**: Production React 18 + Vite trade portal served same-origin at `/portal/` featuring landing page with live statistics, parts catalogue, draft cart with 18% GST ledger math, orders ledger, ML reorder recommendations, and Groq assistant (`frontend`).

### Unattempted Tracks (As Permitted for AI/ML Track)
- **Part B — Supplier Sync Feed**: The mock supplier sync client and feed reconciliation were not attempted.

---

## Tech Stack
- **Backend Core**: Python 3.12, Django 4.2+, Django REST Framework, PostgreSQL (`psycopg[binary]`, `dj-database-url`).
- **Frontend Portal**: React 18, React Router 6 (`HashRouter`), Vite, pure Vanilla CSS design system, zero external UI/chart/icon libraries.
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

## Frontend
The dealer trade portal and counter staff desk is built with **React 18 + Vite** (JavaScript) in `frontend/`. It is served same-origin directly by Django at `/portal/`.

- **Access URL**: `http://localhost:8000/portal/` (Landing page at `#/`, catalogue at `#/catalogue`)
- **Dependencies**: Restricted strictly to `react`, `react-dom`, and `react-router-dom` (`HashRouter`).
- **Styling**: Single shared `:root` design token system in Vanilla CSS, no UI kits, no Tailwind, no external icon fonts.
- **Serving**: Handled same-origin in Django core (`core.views.portal_serve`) without requiring Node.js or CORS at runtime.

### How to Rebuild
```bash
cd frontend
npm ci
npm run build
```

> **Note on Build Artifacts:** The grader does not execute `npm`. Therefore, the compiled production bundle (`frontend/dist/`) is committed to the repository so the portal loads immediately upon running `python manage.py runserver 0.0.0.0:8000 --noreload` on a fresh checkout. `node_modules` is excluded via `.gitignore`.

---

## Testing & Verification

### Run Django Unit Test Suite
```bash
python manage.py test
```
*Executes all 47 test cases across Core, Forecasts, Assistant, and Order Engine (including concurrency and idempotency) in ~15 seconds.*

### Run Official Smoke Test
```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
```
*Verifies all 10 checks across Core endpoints, Assistant contract response, and Forecasting CSV / APIs.*

---

## Order Engine Architecture (`orders/`)

The full order lifecycle engine (Part A2) implements robust concurrency control and state management conforming strictly to API Contract Sections 7.1–7.5:
- **State Flow**: Strict lifecycle transitions (`DRAFT -> CONFIRMED -> DISPATCHED -> DELIVERED` and `DRAFT / CONFIRMED -> CANCELLED`). Prohibited transitions reject with HTTP 409 `INVALID_TRANSITION`. Attempting to edit a non-draft order returns HTTP 409 `ORDER_LOCKED`.
- **Concurrency & Deadlock Prevention**: Employs `transaction.atomic()` with `select_for_update()` on the `Order` row and all involved `Inventory` rows. Inventory row locks are acquired in strictly deterministic `product_id` ascending order to prevent distributed deadlocks under concurrent multi-line orders.
- **All-or-Nothing Stock Allocation**: Before confirming, all lines are checked against available inventory. If any SKU lacks stock, no stock is deducted and HTTP 409 `INSUFFICIENT_STOCK` is returned itemizing every short line.
- **Exact-Once Stock Restoration**: Cancelling a `CONFIRMED` order restores physical warehouse quantities exactly once via the `order.stock_restored` guard. Cancelling a `DRAFT` order modifies no stock.
- **Permanent Price Lock**: Unit prices on `DRAFT` orders reflect live catalogue prices. Upon transition to `CONFIRMED` (or `CANCELLED` from draft), `unit_price` is permanently snapshotted into `OrderItem.unit_price`. Subsequent catalogue price changes never alter confirmed orders.
- **Idempotency**: Clients sending an `Idempotency-Key` header on `POST /api/orders/` receive exact-once creation semantics backed by a database unique constraint. Replaying the identical payload returns the original order (HTTP 200/201); conflicting payloads return HTTP 409 `IDEMPOTENCY_CONFLICT`.
- **Atomic Order Numbering**: Sequential `ORD-YYYYMMDD-NNNN` identifiers partitioned daily in Asia/Kolkata timezone with atomic row locking on `OrderNumberCounter`.

---

## LLM Provider & Architecture

- **Provider**: **Groq Cloud**
- **Default Model**: `openai/gpt-oss-120b` (specified in `dealerdesk/settings.py:98`)
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
| `PATCH` | `/api/products/{sku}/` | Partial product update (e.g. price) |
| `PUT` | `/api/inventory/{sku}/` | Update physical stock for a product |
| `GET` | `/api/dealers/` | Paginated list of dealerships |
| `POST` | `/api/dealers/` | Register new dealership |
| `POST` | `/api/orders/` | Create a DRAFT purchase order (optional `Idempotency-Key`) |
| `GET` | `/api/orders/{order_number}/` | Retrieve purchase order by number |
| `PUT` | `/api/orders/{order_number}/` | Replace items on a DRAFT order |
| `GET` | `/api/orders/` | List orders (filterable by dealer/status) |
| `POST` | `/api/orders/{order_number}/confirm/` | Confirm order with all-or-nothing stock deduction & price lock |
| `POST` | `/api/orders/{order_number}/dispatch/` | Dispatch confirmed order |
| `POST` | `/api/orders/{order_number}/deliver/` | Mark dispatched order as delivered |
| `POST` | `/api/orders/{order_number}/cancel/` | Cancel draft or confirmed order (restores stock once for confirmed) |
| `POST` | `/api/assistant/chat/` | Conversational Dealer Assistant with tool calling |
| `GET` | `/api/forecast/{sku}/` | 4-week demand forecast for a SKU |
| `GET` | `/api/reorder-suggestions/` | Live replenishment suggestions for 40 SKUs |

---

## Project Structure
```
DealerDesk/
├── catalog/               # Products and Inventory models, views, serializers
├── dealers/               # Dealership profiles and credit allocation
├── orders/                # Order engine state machine, concurrency locks, idempotency, GST arithmetic
├── forecasts/             # Forecast read API and live reorder suggestions engine
├── assistant/             # GenAI Assistant: tools, BM25 retrieval, grounding, agent loop
├── core/                  # Health endpoint and idempotent seed_data management command
├── common/                # Custom exception handler, money formatters, pagination
├── dealerdesk/            # Project configuration, root settings, URL configuration
├── frontend/              # React 18 + Vite frontend SPA
│   ├── dist/              # Committed production build served by Django at /portal/
│   ├── src/               # React components, pages, context, and styles
│   ├── package.json       # Allowed dependencies (react, react-dom, react-router-dom)
│   └── vite.config.js     # Base /portal/ and API dev proxy config
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
│   ├── phase_a2_notes.md  # Phase A2 Order Engine architecture & state machine
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
4. **Order Engine Concurrency**: Local development runs on SQLite where table-level file locking can experience contention under high parallel thread bursts. Production runs on PostgreSQL with true row-level locking via `select_for_update()`. For SQLite development, WAL mode and connection `busy_timeout` are enabled via `orders.apps.configure_sqlite_connection` with jitter retry backoff.
5. **Credit Limit**: Omitted from order confirmation per API Contract Sections 3 and 7.1–7.5, which do not specify credit limit checks or error codes for purchase order transitions.

---

## Video Walkthrough
Video: `<VIDEO_LINK>`
*(See [docs/video_script.md](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/docs/video_script.md) for the timed 5-minute spoken walkthrough script).*

