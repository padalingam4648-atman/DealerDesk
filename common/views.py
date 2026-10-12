from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def api_not_found(request, *args, **kwargs):
    """Fallback handler for unmapped /api/ routes to ensure standard JSON error shape."""
    return JsonResponse(
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found.",
                "details": [],
            }
        },
        status=404,
    )
