from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.exceptions import NotFoundError, ValidationError
from common.pagination import StandardPagination
from orders.models import Order
from orders.services import create_draft_order
from orders.serializers import OrderSerializer

VALID_STATUSES = {"DRAFT", "CONFIRMED", "DISPATCHED", "DELIVERED", "CANCELLED"}


class OrderListCreateView(APIView):
    """
    POST /api/orders/ - Create a new DRAFT order.
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

        # Call the core service function
        order = create_draft_order(dealer_or_id=dealer_id, items=items)

        # Re-fetch with prefetch_related for serialization
        order = (
            Order.objects.select_related("dealer")
            .prefetch_related("items__product")
            .get(id=order.id)
        )
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """
    GET /api/orders/{order_number}/ - Retrieve order details by order_number.
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
