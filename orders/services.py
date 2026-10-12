import time
from zoneinfo import ZoneInfo
from django.db import transaction, IntegrityError
from django.utils import timezone

from common.exceptions import ValidationError
from catalog.models import Product
from dealers.models import Dealer
from orders.models import Order, OrderItem, OrderNumberCounter


def generate_order_number() -> str:
    """
    Generate an atomic, sequential order number ORD-YYYYMMDD-NNNN for today in Asia/Kolkata timezone.
    Guarantees uniqueness under concurrent creation and restarts at 0001 daily.
    """
    ist = ZoneInfo("Asia/Kolkata")
    today = timezone.now().astimezone(ist).date()

    for attempt in range(5):
        try:
            with transaction.atomic():
                counter = (
                    OrderNumberCounter.objects.select_for_update()
                    .filter(date=today)
                    .first()
                )
                if counter is None:
                    # Attempt to create or retrieve if another thread created it
                    counter, _ = OrderNumberCounter.objects.get_or_create(
                        date=today,
                        defaults={"last_sequence": 0},
                    )
                    # Re-lock row
                    counter = (
                        OrderNumberCounter.objects.select_for_update()
                        .filter(id=counter.id)
                        .first()
                    )

                counter.last_sequence += 1
                counter.save(update_fields=["last_sequence"])
                seq = counter.last_sequence
                return f"ORD-{today.strftime('%Y%m%d')}-{seq:04d}"
        except IntegrityError:
            if attempt == 4:
                raise
            time.sleep(0.05)

    raise RuntimeError("Failed to generate order number after multiple attempts.")


def create_draft_order(dealer_or_id: Dealer | int, items: list[dict]) -> Order:
    """
    Create a DRAFT order with line items.
    
    Validations:
    - Dealer must exist
    - Items must be a non-empty list
    - Each quantity must be a strict integer >= 1
    - Every SKU must exist in the product catalog
    - No duplicate SKUs allowed in the same order
    
    Stock is not modified. Unit price is left null for DRAFT.
    """
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

    # 2. Validate items collection
    if not isinstance(items, list) or len(items) == 0:
        raise ValidationError(
            message="An order must contain at least one item.",
            details=["items: Items list cannot be empty."],
        )

    # 3. Validate item structures, quantities, and check for duplicates
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
        # Reject booleans (in Python isinstance(True, int) is True)
        if isinstance(raw_qty, bool) or not isinstance(raw_qty, int) or raw_qty < 1:
            raise ValidationError(
                message="Item quantity must be an integer greater than or equal to 1.",
                details=[f"items[{index}].quantity: Must be a positive integer (got {raw_qty!r})."],
            )

        cleaned_items.append((sku, raw_qty))

    # 4. Validate that all SKUs exist in catalogue
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

    # 5. Create Order atomically
    with transaction.atomic():
        order_number = generate_order_number()
        order = Order.objects.create(
            order_number=order_number,
            dealer=dealer,
            status="DRAFT",
        )
        order_items = [
            OrderItem(
                order=order,
                product=products_by_sku[sku],
                quantity=qty,
                unit_price=None,  # null while DRAFT; locked on confirmation in later phase
            )
            for sku, qty in cleaned_items
        ]
        OrderItem.objects.bulk_create(order_items)

    return order
