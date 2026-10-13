from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, Http404
from django.views.static import serve


def health(request):
    """GET /api/health/ — the grader polls this until your app is ready."""
    return JsonResponse({"status": "ok"})


def portal_serve(request, path=""):
    """
    Serves the pre-built React SPA at /portal/.
    Assets are served directly from frontend/dist/.
    HTML requests and subpaths fallback to frontend/dist/index.html so HashRouter works seamlessly.
    """
    dist_dir = settings.BASE_DIR / "frontend" / "dist"

    clean_path = path.strip("/")

    if not clean_path or clean_path in ("app", "index.html"):
        return serve(request, "index.html", document_root=dist_dir)

    target_file = dist_dir / clean_path
    if target_file.is_file():
        return serve(request, clean_path, document_root=dist_dir)

    # For any SPA sub-path, return index.html
    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return serve(request, "index.html", document_root=dist_dir)

    raise Http404("Portal asset not found.")
