from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.exceptions import NotFoundError
from common.pagination import StandardPagination
from dealers.models import Dealer
from dealers.serializers import DealerSerializer


class DealerListCreateView(APIView):
    """
    GET /api/dealers/ - Paginated list of registered dealers.
    POST /api/dealers/ - Register a new dealer.
    """
    pagination_class = StandardPagination

    def get(self, request):
        queryset = Dealer.objects.all().order_by("id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is not None:
            serializer = DealerSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = DealerSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DealerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


class DealerDetailView(APIView):
    """
    GET /api/dealers/{id}/ - Dealer details by ID.
    """
    def get(self, request, pk):
        try:
            dealer = Dealer.objects.get(pk=pk)
        except (Dealer.DoesNotExist, ValueError):
            raise NotFoundError(message=f"Dealer with ID {pk} not found.")

        serializer = DealerSerializer(dealer)
        return Response(serializer.data, status=status.HTTP_200_OK)
