"""Modal hosting wrapper (M7). Thin wrapper — no app logic lives here.

Imports the same FastAPI ``app`` object the container serves
(``backend/app/main.py``) and exposes it through Modal's ASGI construct
when the ``modal`` package is installed. Import-validates without
``modal`` installed: the ``modal`` import is guarded, and a clear error
is raised only on the deploy path (calling ``build_modal_asgi`` /
accessing ``asgi_app`` without ``modal``).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.main import app  # noqa: E402  (same object the container serves)

try:
    import modal  # type: ignore[import-not-found]
except ImportError:
    modal = None  # type: ignore[assignment]


def build_modal_asgi(app_obj=app):
    """Expose the ASGI app through Modal. Requires the ``modal`` package."""
    if modal is None:
        raise RuntimeError(
            "The 'modal' package is not installed. "
            "Install it with `pip install modal` and run `modal setup` "
            "before deploying modal_app.py."
        )
    modal_app = modal.App("zeroshot-qc")
    return modal_app.function(image=modal.Image.debian_slim())(modal.asgi_app()(lambda: app_obj))


asgi_app = None
if modal is not None:
    asgi_app = build_modal_asgi()
