from django.urls import path
from orders.views import OrderListCreateView, OrderDetailView

urlpatterns = [
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<str:order_number>/", OrderDetailView.as_view(), name="order-detail"),
]
