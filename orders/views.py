import time
from django.db import OperationalError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.exceptions import NotFoundError, ValidationError
from common.pagination import StandardPagination
from orders.models import Order
from orders.services import (
    create_draft_order_with_idempotency,
    edit_draft_order,
    confirm_order,
    dispatch_order,
    deliver_order,
    cancel_order,
)
from orders.serializers import OrderSerializer

VALID_STATUSES = {"DRAFT", "CONFIRMED", "DISPATCHED", "DELIVERED", "CANCELLED"}


def get_order_with_relations(order_id: int) -> Order:
    """
    Retrieve an order with relations for serialization, with retry on transient SQLite lock collisions.
    """
    for attempt in range(25):
        try:
            return (
                Order.objects.select_related("dealer")
                .prefetch_related("items__product")
                .get(id=order_id)
            )
        except OperationalError:
            if attempt == 24:
                raise
            time.sleep(0.01 * (attempt + 1))


class OrderListCreateView(APIView):
    """
    POST /api/orders/ - Create a new DRAFT order with optional Idempotency-Key header.
    GET /api/orders/ - Paginated list of orders, newest first, filterable by dealer_id and status.
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = (
            Order.objects.select_related("dealer")
            .prefetch_related("items__product")
            .all()
            .order_by("-created_at")
        )

        dealer_id = request.query_params.get("dealer_id")
        if dealer_id:
            try:
                queryset = queryset.filter(dealer_id=int(dealer_id))
            except ValueError:
                raise ValidationError("Invalid dealer_id filter.", details=["dealer_id: Must be an integer."])

        order_status = request.query_params.get("status")
        if order_status:
            order_status = order_status.strip().upper()
            if order_status not in VALID_STATUSES:
                raise ValidationError(
                    f"Invalid status '{order_status}'.",
                    details=[f"status: Must be one of {sorted(list(VALID_STATUSES))}."],
                )
            queryset = queryset.filter(status=order_status)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError(
                "Request body must be a JSON object.",
                details=["body: Must be a JSON object with 'dealer_id' and 'items'."],
            )

        dealer_id = request.data.get("dealer_id")
        items = request.data.get("items")

        if dealer_id is None:
            raise ValidationError(
                "Field 'dealer_id' is required.",
                details=["dealer_id: This field is required."],
            )

        if items is None:
            raise ValidationError(
                "Field 'items' is required.",
                details=["items: This field is required."],
            )

        # Check for Idempotency-Key header (Contract 7.5)
        idempotency_key = (
            request.headers.get("Idempotency-Key")
            or request.META.get("HTTP_IDEMPOTENCY_KEY")
        )
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key:
                idempotency_key = None

        order, is_replay = create_draft_order_with_idempotency(
            dealer_or_id=dealer_id,
            items=items,
            idempotency_key=idempotency_key,
            request_payload=request.data,
        )

        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        response_status = status.HTTP_200_OK if is_replay else status.HTTP_201_CREATED
        return Response(serializer.data, status=response_status)


class OrderDetailView(APIView):
    """
    GET /api/orders/{order_number}/ - Retrieve order details by order_number.
    PUT /api/orders/{order_number}/ - Replace all items on a DRAFT order.
    """
    def get(self, request, order_number):
        try:
            order = (
                Order.objects.select_related("dealer")
                .prefetch_related("items__product")
                .get(order_number=order_number)
            )
        except Order.DoesNotExist:
            raise NotFoundError(message=f"Order '{order_number}' not found.")

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, order_number):
        if not isinstance(request.data, dict):
            raise ValidationError(
                "Request body must be a JSON object.",
                details=["body: Must be a JSON object with 'items'."],
            )

        items = request.data.get("items")
        if items is None:
            raise ValidationError(
                "Field 'items' is required.",
                details=["items: This field is required."],
            )

        order = edit_draft_order(order_or_number=order_number, items=items)
        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderConfirmView(APIView):
    """
    POST /api/orders/{order_number}/confirm/ - Confirm a DRAFT order.
    """
    def post(self, request, order_number):
        order = confirm_order(order_or_number=order_number)
        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderDispatchView(APIView):
    """
    POST /api/orders/{order_number}/dispatch/ - Dispatch a CONFIRMED order.
    """
    def post(self, request, order_number):
        order = dispatch_order(order_or_number=order_number)
        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderDeliverView(APIView):
    """
    POST /api/orders/{order_number}/deliver/ - Deliver a DISPATCHED order.
    """
    def post(self, request, order_number):
        order = deliver_order(order_or_number=order_number)
        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderCancelView(APIView):
    """
    POST /api/orders/{order_number}/cancel/ - Cancel a DRAFT or CONFIRMED order.
    """
    def post(self, request, order_number):
        order = cancel_order(order_or_number=order_number)
        order = get_order_with_relations(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)
