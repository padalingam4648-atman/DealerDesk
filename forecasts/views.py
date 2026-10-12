from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from common.exceptions import NotFoundError
from forecasts.services import get_sku_forecast, compute_reorder_suggestions


class ForecastDetailView(APIView):
    """
    GET /api/forecast/{sku}/ - 4-week future demand forecast for a specified SKU.
    Returns 404 NOT_FOUND if the SKU does not exist or is not a forecast SKU.
    """
    def get(self, request, sku):
        forecast_data = get_sku_forecast(sku)
        if not forecast_data:
            raise NotFoundError(message=f"Forecast for SKU '{sku}' not found.")

        return Response(forecast_data, status=status.HTTP_200_OK)


class ReorderSuggestionsView(APIView):
    """
    GET /api/reorder-suggestions/ - List of reorder suggestions for all 40 forecast SKUs
    incorporating live on-hand stock and lead-time safety stock calculations.
    """
    def get(self, request):
        results = compute_reorder_suggestions()
        return Response({"results": results}, status=status.HTTP_200_OK)
