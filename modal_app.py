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
    return modal_app.function(image=modal_image)(modal.asgi_app()(lambda: app_obj))


if modal is not None:
    # Module scope so `modal deploy modal_app.py` discovers the App.
    modal_app = modal.App("zeroshot-qc")
    modal_image = modal.Image.debian_slim().pip_install_from_requirements(
        "backend/requirements.txt"
    )

    @modal_app.function(image=modal_image)
    @modal.asgi_app()
    def asgi_app():
        return app
else:
    modal_app = None
    modal_image = None
    asgi_app = None
