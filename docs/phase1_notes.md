# Phase 1: Backend Core Architecture & Design Decisions

## 1. Overview
DealerDesk Phase 1 implements the backend core for spare parts catalog, warehouse inventory tracking, dealership profiles, and draft order management. The system is built with Django, Django REST Framework, and PostgreSQL.

---

## 2. Domain Models and Schema Design

### Product (`catalog.models.Product`)
Represents motorcycle and automotive spare parts.
- **Fields**:
  - `sku`: `CharField(max_length=40, unique=True, db_index=True)` - Unique part SKU.
  - `name`: `CharField(max_length=255)` - Human-readable name.
  - `category`: `CharField(max_length=100, db_index=True)` - Category (e.g. Brakes, Transmission).
  - `brand`: `CharField(max_length=100, db_index=True)` - Manufacturer brand.
  - `vehicle_fitment`: `CharField(max_length=255, db_index=True)` - Targeted motorcycle model.
  - `price`: `DecimalField(max_digits=12, decimal_places=2)` - Unit catalogue price.
  - `description`: `TextField(blank=True)` - Untrusted text stored verbatim.
  - `created_at`, `updated_at`: Timestamps.
- **Constraints**:
  - `CheckConstraint(price > 0)`: Enforces positive pricing at the database level.

### Inventory (`catalog.models.Inventory`)
Tracks on-hand physical stock for each product.
- **Fields**:
  - `product`: `OneToOneField(Product, on_delete=models.CASCADE, related_name="inventory")`
  - `quantity`: `PositiveIntegerField(default=0)`
  - `updated_at`: Timestamp.
- **Constraints**:
  - `CheckConstraint(quantity >= 0)`: Prevents negative stock.
- **`on_delete=CASCADE` Rationale**:
  An inventory record represents physical stock exclusively for a specific product. If a product is permanently removed from the catalogue, its warehouse stock record has no independent business meaning and must be removed.

### Dealer (`dealers.models.Dealer`)
Stores dealership profile, contact information, and credit allocation.
- **Fields**:
  - `dealer_code`: `CharField(max_length=50, unique=True, db_index=True)`
  - `name`: `CharField(max_length=255)`
  - `city`, `phone`, `email`, `gstin`: Optional contact and taxation fields.
  - `credit_limit`: `DecimalField(max_digits=12, decimal_places=2, default=0.00)`
- **Constraints**:
  - `CheckConstraint(credit_limit >= 0)`: Credit limit cannot be negative.

### Order (`orders.models.Order`)
Container for purchase orders created by or for dealerships.
- **Fields**:
  - `order_number`: `CharField(max_length=50, unique=True, db_index=True)` formatted as `ORD-YYYYMMDD-NNNN`.
  - `dealer`: `ForeignKey(Dealer, on_delete=models.PROTECT, related_name="orders")`
  - `status`: `CharField(choices=['DRAFT', 'CONFIRMED', 'DISPATCHED', 'DELIVERED', 'CANCELLED'], default='DRAFT', db_index=True)`
  - `stock_restored`: `BooleanField(default=False)` - Guards exact-once stock restoration on cancellation.
  - `created_at`, `updated_at`: ISO 8601 timestamps.
- **`on_delete=PROTECT` Rationale**:
  Orders represent legal and financial transaction records. Deleting a dealership that has associated orders would orphan financial histories and compromise auditability; hence dealer deletion is protected.

### OrderItem (`orders.models.OrderItem`)
Individual line item in an order.
- **Fields**:
  - `order`: `ForeignKey(Order, on_delete=models.CASCADE, related_name="items")`
  - `product`: `ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")`
  - `quantity`: `PositiveIntegerField`
  - `unit_price`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)` (null while DRAFT; locked upon confirmation).
- **Constraints**:
  - `CheckConstraint(quantity >= 1)`: Line items must order at least 1 unit.
  - `UniqueConstraint(order, product)`: Prevents duplicate SKU entries in the same order.
- **`on_delete` Rationales**:
  - `order -> CASCADE`: Line items are child components of an order. If an order is deleted, all constituent items must be deleted.
  - `product -> PROTECT`: Preserves historical sales records. Deleting a catalog product that has been ordered would invalidate transaction history.

### OrderNumberCounter (`orders.models.OrderNumberCounter`)
- **Fields**:
  - `date`: `DateField(unique=True, db_index=True)` (Asia/Kolkata date).
  - `last_sequence`: `PositiveIntegerField(default=0)`.
- **Purpose**:
  Maintains an atomic sequence counter per date in IST. Incremented under `select_for_update` within `transaction.atomic` to guarantee unique, collision-free `ORD-YYYYMMDD-NNNN` identifiers under high concurrency.

### IdempotencyRecord (`orders.models.IdempotencyRecord`)
- **Fields**:
  - `key`: `CharField(max_length=255, unique=True, db_index=True)`
  - `request_hash`: `CharField(max_length=64)` - SHA-256 hash of canonicalized JSON request payload.
  - `order`: `ForeignKey(Order, on_delete=models.CASCADE, related_name="idempotency_records")`
  - `created_at`: Timestamp.
- **Purpose**:
  Enforces exact-once semantics on `POST /api/orders/` under parallel duplicate requests and detects payload conflicts.

---

## 3. Financial Logic & GST Compliance
- **File**: `orders/money.py`
- Pure decimal arithmetic using Python `Decimal`:
  - `line_subtotal = quantize_money(unit_price * quantity)`
  - `line_tax = quantize_money(line_subtotal * Decimal("0.18"))` rounded per line using `ROUND_HALF_UP` (e.g. `0.225 -> 0.23`).
  - `line_total = line_subtotal + line_tax`
  - `subtotal = sum(line_subtotal)`
  - `tax_total = sum(line_tax)`
  - `grand_total = subtotal + tax_total`
- All JSON financial values serialize as 2-decimal strings (`"1459.50"`).

---

## 4. Key Logic File Locations
| Component | File Path |
|---|---|
| Contract Exception Handler | `common/exceptions.py` |
| Money Helpers & Field | `common/money.py` |
| Financial Calculation Core | `orders/money.py` |
| Order Creation Service | `orders/services.py:create_draft_order` |
| Atomic Order Number Generator | `orders/services.py:generate_order_number` |
| Idempotent Seeding Command | `core/management/commands/seed_data.py` |
| Standard Pagination | `common/pagination.py` |

---

## 5. Seed Data Implementation
- **Command**: `python manage.py seed_data`
- Handles CSV quirks: `utf-8-sig` encoding, whitespace trimming, CRLF tolerance, robust Decimal parsing.
- Uses `update_or_create` wrapped in `transaction.atomic`.
- Sets initial inventory only on initial creation (`created=True`), ensuring subsequent runs do not overwrite live warehouse stock counts.
