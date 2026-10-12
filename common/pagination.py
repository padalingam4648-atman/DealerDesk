from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from common.exceptions import NotFoundError


class StandardPagination(PageNumberPagination):
    """
    Standard pagination for DealerDesk APIs:
    - default page_size: 20
    - max page_size: 100
    - query params: page, page_size
    - format: count, next, previous, results
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view=view)
        except Exception as exc:
            # When page number is invalid / out of range, DRF raises NotFound
            raise NotFoundError(message="Invalid page.")

    def get_paginated_response(self, data):
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })
