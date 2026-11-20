"""Read-only review app for the public output of a single completed HUD job."""
import json
import os
from pathlib import Path
import secrets

from django.conf import settings
from django.core.asgi import get_asgi_application
from django.http import FileResponse, JsonResponse
from django.urls import path
from django.views.decorators.http import require_safe

ROOT = Path(__file__).resolve().parent / "proof"
settings.configure(DEBUG=False, SECRET_KEY=secrets.token_hex(32), ROOT_URLCONF=__name__,
                   ALLOWED_HOSTS=["*"], MIDDLEWARE=["django.middleware.security.SecurityMiddleware"])


@require_safe
def preview(request):
    return FileResponse((ROOT/"screen.html").open("rb"),content_type="text/html; charset=utf-8")


@require_safe
def metrics(request):
    author = json.loads((ROOT/"authoring.json").read_text())
    geometry = json.loads((ROOT/"geometry.json").read_text())
    return JsonResponse({"project": author["project"], "commit": author["game_revision"],
                         "model_calls": author["model_calls"], "tokens": author["inference_tokens"],
                         "elapsed_ms": author["authoring_ms"], "viewports": len(geometry["viewports"]),
                         "rejections": sum(not step["accepted"] for step in author["trace"]),
                         "layout_failures": sum(bool(row["violations"]) for row in geometry["viewports"])})


urlpatterns = [path("", preview), path("metrics", metrics)]
application = get_asgi_application()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application,host=os.getenv("HUD_BIND","127.0.0.1"),port=int(os.getenv("DATABRICKS_APP_PORT","8000")))
