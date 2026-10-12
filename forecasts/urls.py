from django.urls import path
from forecasts.views import ForecastDetailView, ReorderSuggestionsView

urlpatterns = [
    path("forecast/<str:sku>/", ForecastDetailView.as_view(), name="forecast-detail"),
    path("reorder-suggestions/", ReorderSuggestionsView.as_view(), name="reorder-suggestions"),
]
