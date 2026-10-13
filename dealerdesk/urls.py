from django.contrib import admin
from django.urls import include, path, re_path
from common.views import api_not_found
from core.views import portal_serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("dealers.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("forecasts.urls")),
    path("api/", include("assistant.urls")),
    # Fallback to ensure all unrecognized /api/ endpoints conform to contract error format
    re_path(r"^api/.*", api_not_found),
    path("portal", portal_serve, {"path": ""}),
    path("portal/", portal_serve, {"path": ""}),
    re_path(r"^portal/(?P<path>.*)$", portal_serve),
]
