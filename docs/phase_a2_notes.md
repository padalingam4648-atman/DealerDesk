# Phase A2: Order Engine Implementation Notes

## 1. Executive Summary & Git Metadata

Phase A2 implements the full, production-grade purchase order state machine and order lifecycle engine for VIKMO DealerDesk, adhering strictly to API Contract Sections 7.1–7.5.

- **Git Branch**: `feature/order-engine`
- **Starting Commit**: `c2615cf1cc698c7e5fd04e52aa29a4d70f88ae97`
- **Status**: Complete, fully audited, and isolated to `orders/` and `docs/phase_a2_notes.md`.
- **Test Suite**: 47/47 tests passing (`python manage.py test`), including 5 multi-threaded concurrency and idempotency tests.
- **Smoke Tests**: 10/10 checks passing on `aiml` track (`python smoke_test.py --track aiml`).

---

## 2. Order Lifecycle State Machine

The order engine enforces the strict state transitions specified in API Contract Section 7.2.

```
       ┌──────────────────┐
       │      DRAFT       │◄──────── edit (PUT /api/orders/{id}/)
       └────────┬─────────┘
                │
         confirm│          cancel
                ├────────────────────────┐
                ▼                        ▼
       ┌──────────────────┐     ┌──────────────────┐
       │    CONFIRMED     │     │    CANCELLED     │ (Terminal)
       └────────┬─────────┘     └──────────────────┘
                │                        ▲
        dispatch│          cancel        │
                ├────────────────────────┘
                ▼
       ┌──────────────────┐
       │    DISPATCHED    │
       └────────┬─────────┘
                │
         deliver│
                ▼
       ┌──────────────────┐
       │    DELIVERED     │ (Terminal)
       └──────────────────┘
```

### Transition Table

| Current Status | Action | Target Status | Stock Effect | Price Effect | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `DRAFT` | `edit` | `DRAFT` | None | Re-evaluated | Full replacement of line items. |
| `DRAFT` | `confirm` | `CONFIRMED` | Deducted | Locked | All-or-nothing stock check. Snapshot catalogue price. |
| `DRAFT` | `cancel` | `CANCELLED` | None | Locked | No stock was ever deducted; inventory is untouched. |
| `CONFIRMED` | `dispatch` | `DISPATCHED` | None | Maintained | Transitions order towards fulfillment. |
| `CONFIRMED` | `cancel` | `CANCELLED` | Restored | Maintained | Inventory restored exactly once (`stock_restored = True`). |
| `DISPATCHED` | `deliver` | `DELIVERED` | None | Maintained | Final delivery confirmation. Terminal state. |
| `DELIVERED` | *Any* | — | — | — | Blocked: HTTP 409 `INVALID_TRANSITION`. |
| `CANCELLED` | *Any* | — | — | — | Blocked: HTTP 409 `INVALID_TRANSITION`. |

### Error Codes and Transition Guarantees
- Any prohibited status transition raises HTTP 409 `INVALID_TRANSITION` ([orders/services.py:40-60](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L40-L60)).
- Attempting to edit a non-DRAFT order via `PUT /api/orders/{order_number}/` raises HTTP 409 `ORDER_LOCKED` ([orders/services.py:51-55](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L51-L55)).

---

## 3. Concurrency, Row Locking, and Deadlock Prevention

### 1. Deterministic Lock Acquisition Order
When confirming an order with multiple line items, competing transactions could deadlock if they acquire row locks in arbitrary order (e.g. Transaction A locks Product 1 then 2; Transaction B locks Product 2 then 1).
To prevent deadlocks:
- Inventory rows are sorted deterministically by `product_id` before querying:
  ```python
  product_ids = sorted(list({item.product_id for item in items}))
  inventories = (
      Inventory.objects.select_for_update()
      .filter(product_id__in=product_ids)
      .order_by("product_id")
  )
  ```
- The `Order` row is locked via `select_for_update()` at the start of the transaction ([orders/services.py:63-81](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L63-L81)).

### 2. Sequential Order Number Generation
Order numbers follow the format `ORD-YYYYMMDD-NNNN` in Asia/Kolkata timezone, restarting at `0001` daily:
- Tracked atomically via `OrderNumberCounter` ([orders/models.py:88-101](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/models.py#L88-L101)).
- Counter row is locked via `select_for_update()`.
- Under SQLite during unit tests, transactional collisions are caught with retry backoff loops to guarantee robustness ([orders/services.py:83-113](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L83-L113)).

---

## 4. Stock Allocation and Exact-Once Cancellation

### All-or-Nothing Stock Check
Confirmation performs an atomic check against `Inventory.quantity` for all order items:
- If **any** item lacks sufficient stock, **none** are deducted.
- The transaction aborts and raises HTTP 409 `INSUFFICIENT_STOCK` with detailed itemization:
  ```json
  {
    "error": {
      "code": "INSUFFICIENT_STOCK",
      "message": "Insufficient stock for one or more items.",
      "details": [
        "BDY-1011: requested 5, available 2"
      ]
    }
  }
  ```

### Exact-Once Stock Restoration
- Model field `Order.stock_restored = models.BooleanField(default=False)` tracks whether physical stock has been credited back to inventory ([orders/models.py:34](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/models.py#L34)).
- Cancelling a `DRAFT` order sets status to `CANCELLED` but **never** modifies inventory stock (drafts never reserve stock).
- Cancelling a `CONFIRMED` order restores `inventory.quantity += item.quantity` and sets `order.stock_restored = True` in a single atomic transaction ([orders/services.py:382-446](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L382-L446)).
- A second cancellation attempt is blocked by `validate_transition` (HTTP 409 `INVALID_TRANSITION`), and the `stock_restored` flag acts as a defense-in-depth guard against double restoration.

---

## 5. Permanent Price Locking

To prevent catalog price changes from mutating past or active purchase orders:
- While an order is `DRAFT`, `OrderItem.unit_price` is calculated dynamically against current catalogue prices.
- When an order is `CONFIRMED` (or `CANCELLED` from `DRAFT`), `OrderItem.unit_price` is permanently snapshotted from `product.price` into the database ([orders/services.py:270-275](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L270-L275)).
- If catalogue prices are later altered via supplier sync or admin edits, confirmed orders retain their original contracted `unit_price`, `subtotal`, `tax_total`, and `grand_total`.

---

## 6. Idempotency Key Handling (`POST /api/orders/`)

Clients can send the `Idempotency-Key` HTTP header on order creation (API Contract Section 7.5).

### Implementation Details ([orders/services.py:175-225](file:///c:/Users/PADALINGAM/Downloads/DealerDesk/orders/services.py#L175-L225))
- **Model**: `IdempotencyRecord` stores `key` (unique), `request_hash` (SHA-256 of canonicalized JSON request payload), `order` (FK CASCADE), and `created_at`.
- **First Request**: Creates both the `Order` and `IdempotencyRecord` atomically. Returns HTTP 201 Created.
- **Replay (Identical Payload)**: Detects matching `key` and matching `request_hash`. Returns the existing order with HTTP 200 OK.
- **Conflict (Mismatched Payload)**: Detects matching `key` but differing `request_hash`. Raises HTTP 409 `IDEMPOTENCY_CONFLICT`:
  ```json
  {
    "error": {
      "code": "IDEMPOTENCY_CONFLICT",
      "message": "Idempotency key '...' has already been used with a different request payload.",
      "details": []
    }
  }
  ```
- **Standard Requests**: When `Idempotency-Key` is absent, standard order creation proceeds normally.

---

## 7. Outdated Statements in Repository Documentation

The following statements in existing documentation now become outdated with Part A2 implemented:

### `README.md`
- **Line 19**:
  > *"Part A2 — Full Order Engine: Confirmed/dispatched transitions, credit limit checks, and concurrency locks were not implemented beyond DRAFT orders."*
  - **Correction**: Part A2 is now implemented on `feature/order-engine` with full state transitions (`DRAFT`, `CONFIRMED`, `DISPATCHED`, `DELIVERED`, `CANCELLED`), deterministic row-level inventory locking, price freezing, exact-once stock restoration, and header-based idempotency.

### `DECISIONS.md`
- **Section 1, Point 5 (Line 17)**:
  > *"unit_price is null while DRAFT; locked on confirm to current product price permanently."*
  - **Correction**: Accurate and now fully implemented. Line items now actively lock `unit_price` at transition time.
- **Section 4, Line 74**:
  > *"It strictly creates DRAFT status orders; no confirmation capability exists."*
  - **Correction**: Phase 3 conversational assistant remains restricted to DRAFT order creation by design for safety, but the core backend order engine now supports the complete lifecycle.
