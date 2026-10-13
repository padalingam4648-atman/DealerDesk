import hashlib
import json
import time
from zoneinfo import ZoneInfo
from django.db import transaction, IntegrityError, OperationalError
from django.utils import timezone

from common.exceptions import (
    ValidationError,
    NotFoundError,
    InsufficientStockError,
    InvalidTransitionError,
    OrderLockedError,
    IdempotencyConflictError,
)
from catalog.models import Product, Inventory
from dealers.models import Dealer
from orders.models import Order, OrderItem, OrderNumberCounter, IdempotencyRecord


# Transition table defining all permitted actions per lifecycle status (Contract Section 7.2)
ALLOWED_TRANSITIONS = {
    "DRAFT": {
        "confirm": "CONFIRMED",
        "cancel": "CANCELLED",
        "edit": "DRAFT",
    },
    "CONFIRMED": {
        "dispatch": "DISPATCHED",
        "cancel": "CANCELLED",
    },
    "DISPATCHED": {
        "deliver": "DELIVERED",
    },
    "DELIVERED": {},
    "CANCELLED": {},
}


def validate_transition(order: Order, action: str) -> str:
    """
    Validate whether `action` is permitted on `order` given its current status.
    Returns target status string if valid, or raises the exact contract exception.
    """
    current_status = order.status
    action_map = ALLOWED_TRANSITIONS.get(current_status, {})

    if action in action_map:
        return action_map[action]

    if action == "edit":
        raise OrderLockedError(
            message=f"Order '{order.order_number}' is {current_status} and cannot be edited. Only DRAFT orders can be edited.",
            details=[f"status: Order is '{current_status}', must be 'DRAFT'."],
        )

    raise InvalidTransitionError(
        message=f"Cannot {action} order '{order.order_number}' with status '{current_status}'.",
        details=[f"transition: Action '{action}' is not allowed from status '{current_status}'."],
    )


def get_order_for_update(order_or_number: Order | str) -> Order:
    """
    Retrieve an order with a row-level lock (select_for_update), raising 404 NOT_FOUND if missing.
    """
    if isinstance(order_or_number, Order):
        return (
            Order.objects.select_for_update()
            .select_related("dealer")
            .get(id=order_or_number.id)
        )
    try:
        return (
            Order.objects.select_for_update()
            .select_related("dealer")
            .get(order_number=order_or_number)
        )
    except Order.DoesNotExist:
        raise NotFoundError(message=f"Order '{order_or_number}' not found.")


def generate_order_number() -> str:
    """
    Generate an atomic, sequential order number ORD-YYYYMMDD-NNNN for today in Asia/Kolkata timezone.
    Guarantees uniqueness under concurrent creation and restarts at 0001 daily.
    """
    ist = ZoneInfo("Asia/Kolkata")
    today = timezone.now().astimezone(ist).date()

    for attempt in range(50):
        try:
            with transaction.atomic():
                counter = (
                    OrderNumberCounter.objects.select_for_update()
                    .filter(date=today)
                    .first()
                )
                if counter is None:
                    counter, _ = OrderNumberCounter.objects.get_or_create(
                        date=today,
                        defaults={"last_sequence": 0},
                    )
                    counter = (
                        OrderNumberCounter.objects.select_for_update()
                        .filter(id=counter.id)
                        .first()
                    )

                counter.last_sequence += 1
                counter.save(update_fields=["last_sequence"])
                seq = counter.last_sequence
                return f"ORD-{today.strftime('%Y%m%d')}-{seq:04d}"
        except (IntegrityError, OperationalError):
            if attempt == 49:
                raise
            time.sleep(0.01 * (attempt + 1))

    raise RuntimeError("Failed to generate order number after multiple attempts.")


def validate_and_clean_items(items: list[dict]) -> tuple[list[tuple[str, int]], dict[str, Product]]:
    """
    Validate item structures, quantities, check for duplicates, and ensure catalog existence.
    Returns: (cleaned_items, products_by_sku_dict)
    """
    if not isinstance(items, list) or len(items) == 0:
        raise ValidationError(
            message="An order must contain at least one item.",
            details=["items: Items list cannot be empty."],
        )

    seen_skus = set()
    cleaned_items = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(
                message="Each item must be an object with 'sku' and 'quantity'.",
                details=[f"items[{index}]: Invalid item format."],
            )

        sku = item.get("sku")
        if not sku or not isinstance(sku, str):
            raise ValidationError(
                message="Each item must have a valid non-empty 'sku'.",
                details=[f"items[{index}].sku: SKU is required."],
            )
        sku = sku.strip()

        if sku in seen_skus:
            raise ValidationError(
                message=f"Duplicate SKU '{sku}' found in order items.",
                details=[f"items: Duplicate SKU '{sku}' is not allowed."],
            )
        seen_skus.add(sku)

        raw_qty = item.get("quantity")
        if isinstance(raw_qty, bool) or not isinstance(raw_qty, int) or raw_qty < 1:
            raise ValidationError(
                message="Item quantity must be an integer greater than or equal to 1.",
                details=[f"items[{index}].quantity: Must be a positive integer (got {raw_qty!r})."],
            )

        cleaned_items.append((sku, raw_qty))

    products_by_sku = {
        p.sku: p for p in Product.objects.filter(sku__in=seen_skus)
    }
    missing_skus = seen_skus - set(products_by_sku.keys())
    if missing_skus:
        missing_list = sorted(list(missing_skus))
        raise ValidationError(
            message=f"Product SKU(s) do not exist: {', '.join(missing_list)}",
            details=[f"items: Product SKU '{s}' not found." for s in missing_list],
        )

    return cleaned_items, products_by_sku


def create_draft_order(
    dealer_or_id: Dealer | int,
    items: list[dict],
    idempotency_key: str | None = None,
    req_hash: str | None = None,
) -> Order:
    """
    Create a DRAFT order with line items.
    Validates dealer, non-empty items, strict positive quantities, and existing unique SKUs.
    Stock is not modified. unit_price is left null for DRAFT.
    Optionally creates an IdempotencyRecord in the same transaction.
    """
    for attempt in range(20):
        try:
            # 1. Resolve dealer
            if isinstance(dealer_or_id, Dealer):
                dealer = dealer_or_id
            else:
                try:
                    dealer = Dealer.objects.get(id=dealer_or_id)
                except (Dealer.DoesNotExist, TypeError, ValueError):
                    raise ValidationError(
                        message=f"Dealer with ID {dealer_or_id} does not exist.",
                        details=[f"dealer_id: Dealer '{dealer_or_id}' does not exist."],
                    )

            # 2. Validate items
            cleaned_items, products_by_sku = validate_and_clean_items(items)

            # 3. Create Order atomically with retry on transient lock collisions
            with transaction.atomic():
                order_number = generate_order_number()
                order = Order.objects.create(
                    order_number=order_number,
                    dealer=dealer,
                    status="DRAFT",
                    stock_restored=False,
                )
                order_items = [
                    OrderItem(
                        order=order,
                        product=products_by_sku[sku],
                        quantity=qty,
                        unit_price=None,  # null while DRAFT; locked permanently on confirmation
                    )
                    for sku, qty in cleaned_items
                ]
                OrderItem.objects.bulk_create(order_items)
                if idempotency_key and req_hash:
                    IdempotencyRecord.objects.create(
                        key=idempotency_key,
                        request_hash=req_hash,
                        order=order,
                    )
                return order
        except OperationalError:
            if attempt == 19:
                raise
            time.sleep(0.01 * (attempt + 1))


def compute_request_hash(payload: dict) -> str:
    """
    Compute a SHA-256 hash of canonicalized JSON request payload.
    """
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def create_draft_order_with_idempotency(
    dealer_or_id: Dealer | int,
    items: list[dict],
    idempotency_key: str | None = None,
    request_payload: dict | None = None,
) -> tuple[Order, bool]:
    """
    Create a DRAFT order, optionally wrapped in exact-once idempotency logic.
    Returns: (Order, is_replay: bool)
    """
    if not idempotency_key:
        order = create_draft_order(dealer_or_id=dealer_or_id, items=items)
        return order, False

    payload_to_hash = (
        request_payload
        if request_payload is not None
        else {"dealer_id": getattr(dealer_or_id, "id", dealer_or_id), "items": items}
    )
    req_hash = compute_request_hash(payload_to_hash)

    # 1. Fast read check outside transaction
    existing = (
        IdempotencyRecord.objects.select_related("order")
        .filter(key=idempotency_key)
        .first()
    )
    if existing:
        if existing.request_hash != req_hash:
            raise IdempotencyConflictError(
                message=f"Idempotency key '{idempotency_key}' was previously used with a different request body.",
                details=["Idempotency-Key: Reused with conflicting request body."],
            )
        return existing.order, True

    # 2. Atomic creation of order and idempotency record inside the exact same transaction
    for attempt in range(50):
        try:
            order = create_draft_order(
                dealer_or_id=dealer_or_id,
                items=items,
                idempotency_key=idempotency_key,
                req_hash=req_hash,
            )
            return order, False

        except IntegrityError:
            # Concurrent race on unique constraint: another thread committed or is committing
            time.sleep(0.02 * (attempt % 5 + 1))
            try:
                rec = (
                    IdempotencyRecord.objects.select_related("order")
                    .filter(key=idempotency_key)
                    .first()
                )
                if rec:
                    if rec.request_hash != req_hash:
                        raise IdempotencyConflictError(
                            message=f"Idempotency key '{idempotency_key}' was previously used with a different request body.",
                            details=["Idempotency-Key: Reused with conflicting request body."],
                        )
                    return rec.order, True
            except OperationalError:
                pass
            if attempt == 49:
                raise

        except OperationalError:
            time.sleep(0.02 * (attempt % 5 + 1))
            try:
                rec = (
                    IdempotencyRecord.objects.select_related("order")
                    .filter(key=idempotency_key)
                    .first()
                )
                if rec:
                    if rec.request_hash != req_hash:
                        raise IdempotencyConflictError(
                            message=f"Idempotency key '{idempotency_key}' was previously used with a different request body.",
                            details=["Idempotency-Key: Reused with conflicting request body."],
                        )
                    return rec.order, True
            except OperationalError:
                pass
            if attempt == 49:
                raise

    raise RuntimeError("Failed to resolve idempotent order creation race condition.")


def edit_draft_order(order_or_number: Order | str, items: list[dict]) -> Order:
    """
    PUT /api/orders/{order_number}/: Replaces all items on a DRAFT order.
    Only allowed while status is DRAFT; otherwise raises ORDER_LOCKED.
    """
    cleaned_items, products_by_sku = validate_and_clean_items(items)

    for attempt in range(50):
        try:
            with transaction.atomic():
                order = get_order_for_update(order_or_number)
                validate_transition(order, "edit")

                # Replace all items
                order.items.all().delete()
                new_order_items = [
                    OrderItem(
                        order=order,
                        product=products_by_sku[sku],
                        quantity=qty,
                        unit_price=None,
                    )
                    for sku, qty in cleaned_items
                ]
                OrderItem.objects.bulk_create(new_order_items)
                order.save(update_fields=["updated_at"])
                return order
        except OperationalError:
            if attempt == 49:
                raise
            time.sleep(0.02 * (attempt % 5 + 1))


def confirm_order(order_or_number: Order | str) -> Order:
    """
    POST /api/orders/{order_number}/confirm/: DRAFT -> CONFIRMED.
    All-or-nothing stock validation, atomic stock deduction, and permanent unit_price locking.
    Inventory rows are locked with select_for_update in consistent product_id order to avoid deadlocks.
    """
    for attempt in range(50):
        try:
            with transaction.atomic():
                order = get_order_for_update(order_or_number)
                validate_transition(order, "confirm")

                items = list(order.items.select_related("product").all())
                if not items:
                    raise ValidationError(
                        message="Order has no items to confirm.",
                        details=["items: Order has no items."],
                    )

                # Lock Inventory rows in strict deterministic order (sorted by product_id)
                product_ids = sorted([item.product_id for item in items])
                inventories = {
                    inv.product_id: inv
                    for inv in Inventory.objects.select_for_update()
                    .filter(product_id__in=product_ids)
                    .order_by("product_id")
                }

                # Validate stock for all lines
                short_lines = []
                msg_sentences = []
                for item in items:
                    inv = inventories.get(item.product_id)
                    available = inv.quantity if inv else 0
                    if item.quantity > available:
                        short_lines.append({
                            "sku": item.product.sku,
                            "requested": item.quantity,
                            "available": available,
                        })
                        msg_sentences.append(
                            f"Insufficient stock for {item.product.name}. Available: {available}, Requested: {item.quantity}"
                        )

                if short_lines:
                    # All-or-nothing: raise exception, transaction automatically rolls back
                    message_text = ". ".join(msg_sentences)
                    raise InsufficientStockError(message=message_text, details=short_lines)

                # Sufficient stock: deduct inventory and lock unit_price permanently
                for item in items:
                    inv = inventories[item.product_id]
                    inv.quantity -= item.quantity
                    inv.save(update_fields=["quantity", "updated_at"])

                    item.unit_price = item.product.price
                    item.save(update_fields=["unit_price"])

                order.status = "CONFIRMED"
                order.save(update_fields=["status", "updated_at"])
                return order
        except OperationalError:
            if attempt == 49:
                raise
            time.sleep(0.02 * (attempt % 5 + 1))


def dispatch_order(order_or_number: Order | str) -> Order:
    """
    POST /api/orders/{order_number}/dispatch/: CONFIRMED -> DISPATCHED.
    """
    for attempt in range(50):
        try:
            with transaction.atomic():
                order = get_order_for_update(order_or_number)
                target_status = validate_transition(order, "dispatch")
                order.status = target_status
                order.save(update_fields=["status", "updated_at"])
                return order
        except OperationalError:
            if attempt == 49:
                raise
            time.sleep(0.02 * (attempt % 5 + 1))


def deliver_order(order_or_number: Order | str) -> Order:
    """
    POST /api/orders/{order_number}/deliver/: DISPATCHED -> DELIVERED.
    """
    for attempt in range(50):
        try:
            with transaction.atomic():
                order = get_order_for_update(order_or_number)
                target_status = validate_transition(order, "deliver")
                order.status = target_status
                order.save(update_fields=["status", "updated_at"])
                return order
        except OperationalError:
            if attempt == 49:
                raise
            time.sleep(0.02 * (attempt % 5 + 1))


def cancel_order(order_or_number: Order | str) -> Order:
    """
    POST /api/orders/{order_number}/cancel/:
    - DRAFT -> CANCELLED (stock untouched, prices locked for audit record)
    - CONFIRMED -> CANCELLED (stock restored to inventory exactly once)
    - Any other status -> INVALID_TRANSITION
    """
    for attempt in range(50):
        try:
            with transaction.atomic():
                order = get_order_for_update(order_or_number)
                target_status = validate_transition(order, "cancel")
                prior_status = order.status

                items = list(order.items.select_related("product").all())

                if prior_status == "CONFIRMED":
                    if not order.stock_restored:
                        product_ids = sorted([item.product_id for item in items])
                        inventories = {
                            inv.product_id: inv
                            for inv in Inventory.objects.select_for_update()
                            .filter(product_id__in=product_ids)
                            .order_by("product_id")
                        }
                        for item in items:
                            inv = inventories.get(item.product_id)
                            if inv:
                                inv.quantity += item.quantity
                                inv.save(update_fields=["quantity", "updated_at"])
                        order.stock_restored = True
                elif prior_status == "DRAFT":
                    # For DRAFT cancellation, freeze current prices on order items for audit trail
                    for item in items:
                        if item.unit_price is None:
                            item.unit_price = item.product.price
                            item.save(update_fields=["unit_price"])

                order.status = target_status
                order.save(update_fields=["status", "stock_restored", "updated_at"])
                return order
        except OperationalError:
            if attempt == 49:
                raise
            time.sleep(0.02 * (attempt % 5 + 1))
