from django.db import models


class Product(models.Model):
    """
    Catalog product representing spare parts and accessories.
    """
    sku = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, db_index=True, blank=True, default="")
    brand = models.CharField(max_length=100, db_index=True, blank=True, default="")
    vehicle_fitment = models.CharField(max_length=255, db_index=True, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0),
                name="product_price_gt_zero",
            )
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Inventory(models.Model):
    """
    Warehouse inventory holding live stock levels for each product.
    """
    # CASCADE: Inventory represents live on-hand physical stock strictly tied to a product.
    # If a product is removed from the catalog, its inventory record has no standalone meaning and is deleted.
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Inventories"
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name="inventory_quantity_gte_zero",
            )
        ]

    def __str__(self):
        return f"{self.product.sku} stock: {self.quantity}"
