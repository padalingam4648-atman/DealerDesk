from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.exceptions import NotFoundError, DuplicateError
from common.pagination import StandardPagination
from catalog.models import Product, Inventory
from catalog.serializers import ProductSerializer, InventoryUpdateSerializer


class ProductListCreateView(APIView):
    """
    GET /api/products/ - Paginated list of products with search, category, and vehicle filters.
    POST /api/products/ - Create a product with initial stock 0.
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Product.objects.select_related("inventory").all().order_by("sku")

        # Filters
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(sku__icontains=search) | Q(name__icontains=search) | Q(brand__icontains=search)
            )

        category = request.query_params.get("category", "").strip()
        if category:
            queryset = queryset.filter(category=category)

        vehicle = request.query_params.get("vehicle", "").strip()
        if vehicle:
            queryset = queryset.filter(vehicle_fitment__icontains=vehicle)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = ProductSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = ProductSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = serializer.save()
        response_serializer = ProductSerializer(product)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    """
    GET /api/products/{sku}/ - Product detail lookup by SKU.
    PATCH /api/products/{sku}/ - Partial update of product. SKU cannot change.
    """
    def get_object(self, sku):
        try:
            return Product.objects.select_related("inventory").get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundError(message=f"Product with SKU '{sku}' not found.")

    def get(self, request, sku):
        product = self.get_object(sku)
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, sku):
        product = self.get_object(sku)
        # Sku cannot change
        update_data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        update_data.pop("sku", None)
        update_data.pop("stock", None)

        serializer = ProductSerializer(product, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)


class InventoryUpdateView(APIView):
    """
    PUT /api/inventory/{sku}/ - Set live stock quantity for a product.
    """
    def put(self, request, sku):
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            raise NotFoundError(message=f"Product with SKU '{sku}' not found.")

        serializer = InventoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_quantity = serializer.validated_data["quantity"]

        with transaction.atomic():
            inventory, _ = Inventory.objects.select_for_update().get_or_create(
                product=product,
                defaults={"quantity": 0},
            )
            inventory.quantity = new_quantity
            inventory.save(update_fields=["quantity", "updated_at"])

        return Response({"sku": product.sku, "quantity": new_quantity}, status=status.HTTP_200_OK)
