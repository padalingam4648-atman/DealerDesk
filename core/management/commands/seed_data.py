import csv
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Product, Inventory
from dealers.models import Dealer


class Command(BaseCommand):
    help = "Load data/catalogue.csv and data/dealers.csv into the database. Idempotent and safe to run multiple times."

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR
        catalogue_path = data_dir / "catalogue.csv"
        dealers_path = data_dir / "dealers.csv"

        self.stdout.write(f"Seeding catalogue from: {catalogue_path}")
        prod_created, prod_updated, prod_skipped = self.seed_catalogue(catalogue_path)

        self.stdout.write(f"Seeding dealers from: {dealers_path}")
        dlr_created, dlr_updated, dlr_skipped = self.seed_dealers(dealers_path)

        total_products = Product.objects.count()
        total_dealers = Dealer.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"Seeding complete!\n"
            f"Products: {prod_created} created, {prod_updated} updated, {prod_skipped} skipped (Total: {total_products})\n"
            f"Dealers: {dlr_created} created, {dlr_updated} updated, {dlr_skipped} skipped (Total: {total_dealers})"
        ))

    def seed_catalogue(self, path):
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return 0, 0, 0

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            with transaction.atomic():
                for row_idx, raw_row in enumerate(reader, start=2):
                    row = {k.strip(): v.strip() for k, v in raw_row.items() if k}
                    sku = row.get("sku", "")
                    name = row.get("name", "")

                    if not sku or not name:
                        self.stdout.write(self.style.WARNING(f"Row {row_idx}: Missing sku or name, skipping."))
                        skipped_count += 1
                        continue

                    # Parse price
                    try:
                        price = Decimal(row.get("price", "0"))
                        if price <= 0:
                            raise ValueError("Price must be > 0")
                    except (InvalidOperation, ValueError) as e:
                        self.stdout.write(self.style.WARNING(f"Row {row_idx} ({sku}): Invalid price '{row.get('price')}', skipping: {e}"))
                        skipped_count += 1
                        continue

                    # Parse initial stock
                    try:
                        stock = int(row.get("stock", "0"))
                        if stock < 0:
                            raise ValueError("Stock must be >= 0")
                    except ValueError as e:
                        self.stdout.write(self.style.WARNING(f"Row {row_idx} ({sku}): Invalid stock '{row.get('stock')}', skipping: {e}"))
                        skipped_count += 1
                        continue

                    category = row.get("category", "")
                    brand = row.get("brand", "")
                    vehicle_fitment = row.get("vehicle_fitment", "")
                    # Treat description text as untrusted data: store it as-is, never execute or interpret it.
                    description = row.get("description", "")

                    product, created = Product.objects.update_or_create(
                        sku=sku,
                        defaults={
                            "name": name,
                            "category": category,
                            "brand": brand,
                            "vehicle_fitment": vehicle_fitment,
                            "price": price,
                            "description": description,
                        },
                    )

                    if created:
                        # Create the Inventory row from the CSV stock ONLY on first creation (do not reset live stock when re-run)
                        Inventory.objects.create(product=product, quantity=stock)
                        created_count += 1
                    else:
                        # Preserve existing live stock if inventory exists; if missing, initialize
                        Inventory.objects.get_or_create(product=product, defaults={"quantity": 0})
                        updated_count += 1

        return created_count, updated_count, skipped_count

    def seed_dealers(self, path):
        if not path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {path}"))
            return 0, 0, 0

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            with transaction.atomic():
                for row_idx, raw_row in enumerate(reader, start=2):
                    row = {k.strip(): v.strip() for k, v in raw_row.items() if k}
                    dealer_code = row.get("dealer_code", "")
                    name = row.get("name", "")

                    if not dealer_code or not name:
                        self.stdout.write(self.style.WARNING(f"Row {row_idx}: Missing dealer_code or name, skipping."))
                        skipped_count += 1
                        continue

                    # Parse credit_limit
                    try:
                        credit_limit = Decimal(row.get("credit_limit", "0"))
                    except (InvalidOperation, ValueError) as e:
                        self.stdout.write(self.style.WARNING(f"Row {row_idx} ({dealer_code}): Invalid credit_limit '{row.get('credit_limit')}', skipping: {e}"))
                        skipped_count += 1
                        continue

                    city = row.get("city", "")
                    phone = row.get("phone", "")
                    email = row.get("email", "")
                    gstin = row.get("gstin", "")

                    _, created = Dealer.objects.update_or_create(
                        dealer_code=dealer_code,
                        defaults={
                            "name": name,
                            "city": city,
                            "phone": phone,
                            "email": email,
                            "gstin": gstin,
                            "credit_limit": credit_limit,
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

        return created_count, updated_count, skipped_count
