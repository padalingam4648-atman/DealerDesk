from django.db import models
from catalog.models import Product
from dealers.models import Dealer


class Order(models.Model):
    """
    Purchase order created by or on behalf of a dealer.
    """
    STATUS_CHOICES = [
        ("DRAFT", "DRAFT"),
        ("CONFIRMED", "CONFIRMED"),
        ("DISPATCHED", "DISPATCHED"),
        ("DELIVERED", "DELIVERED"),
        ("CANCELLED", "CANCELLED"),
    ]

    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    # PROTECT: Orders represent legal financial records and audit trails.
    # A dealer with existing orders must not be deleted to prevent orphaning transaction history.
    dealer = models.ForeignKey(
        Dealer,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )
    # Flag tracking whether stock has been restored to inventory upon cancellation.
    # Ensures stock restoration executes exactly once and protects against double restoration.
    stock_restored = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number} ({self.status})"


class OrderItem(models.Model):
    """
    Individual line item in an order.
    """
    # CASCADE: Line items are lifecycle components of an order.
    # If the parent order is deleted, all constituent items should be deleted with it.
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    # PROTECT: Prevents deletion of products that are referenced in order items,
    # ensuring historical order and pricing auditability is preserved.
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    # unit_price is null while DRAFT; locked on confirm to current product price permanently.
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1),
                name="order_item_quantity_gte_one",
            ),
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_order_product",
            ),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.product.sku} x {self.quantity}"


class OrderNumberCounter(models.Model):
    """
    Daily counter tracking the sequence number for order generation in Asia/Kolkata timezone.
    Sequence restarts at 0001 daily.
    """
    date = models.DateField(unique=True, db_index=True)
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Order Number Counter"

    def __str__(self):
        return f"{self.date}: {self.last_sequence}"


class IdempotencyRecord(models.Model):
    """
    Records Idempotency-Key payloads and resulting orders to enforce
    exact-once order creation semantics under concurrent and repeated requests.
    """
    key = models.CharField(max_length=255, unique=True, db_index=True)
    request_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of the canonicalized JSON request payload.",
    )
    # CASCADE: Idempotency records are strictly tied to the created order lifecycle.
    # If an order is purged (e.g. test cleanup), the idempotency record cascades with it.
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Idempotency Record"

    def __str__(self):
        return f"{self.key} -> {self.order.order_number}"

