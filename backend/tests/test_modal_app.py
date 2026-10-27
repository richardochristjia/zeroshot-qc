"""Credential-free tests for modal_app.py (M7).

The wrapper must expose a module-level ``modal.App`` (so
``modal deploy modal_app.py`` discovers it) whose image installs
``backend/requirements.txt`` (so the cold start has the backend deps),
and must import safely without the ``modal`` package installed.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODAL_APP_PATH = REPO_ROOT / "modal_app.py"


def _make_fake_modal(record):
    """Build a stub ``modal`` module recording image construction."""
    fake = types.ModuleType("modal")

    class FakeImage:
        def __init__(self, reqs=()):
            self.reqs = list(reqs)

        @classmethod
        def debian_slim(cls):
            return cls()

        def pip_install_from_requirements(self, req_file):
            record.setdefault("requirements", []).append(req_file)
            return FakeImage(self.reqs + [req_file])

    class FakeApp:
        def __init__(self, name):
            self.name = name
            self.seen_images = []

        def function(self, image=None):
            self.seen_images.append(image)

            def deco(fn):
                return fn

            return deco

    def asgi_app():
        def deco(fn):
            fn._modal_asgi_wrapped = True
            return fn

        return deco

    fake.Image = FakeImage
    fake.App = FakeApp
    fake.asgi_app = asgi_app
    fake.FakeApp = FakeApp
    return fake


def _load_wrapper(monkeypatch, modal_module, tag):
    if modal_module is None:
        # `import modal` raises ImportError when the entry is None.
        monkeypatch.setitem(sys.modules, "modal", None)
    else:
        monkeypatch.setitem(sys.modules, "modal", modal_module)
    name = f"modal_app_under_test_{tag}"
    monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location(name, MODAL_APP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_module_level_app_exists(monkeypatch):
    """`modal deploy` needs a module-scope App, not a closure local."""
    record = {}
    module = _load_wrapper(monkeypatch, _make_fake_modal(record), "scoped")
    assert isinstance(module.modal_app, module.modal.FakeApp)
    assert module.modal_app.name == "zeroshot-qc"


def test_image_installs_backend_requirements(monkeypatch):
    """The Modal image must install backend/requirements.txt."""
    record = {}
    module = _load_wrapper(monkeypatch, _make_fake_modal(record), "image")
    assert "backend/requirements.txt" in record.get("requirements", [])
    assert "backend/requirements.txt" in module.modal_image.reqs
    assert module.modal_app.seen_images and module.modal_app.seen_images[0] is (
        module.modal_image
    )


def test_module_level_asgi_function(monkeypatch):
    """A module-level asgi function must be decorated through the App."""
    record = {}
    module = _load_wrapper(monkeypatch, _make_fake_modal(record), "asgi")
    assert callable(module.asgi_app)
    assert getattr(module.asgi_app, "_modal_asgi_wrapped", False) is True


def test_without_modal_import_guard(monkeypatch):
    """Without `modal` installed: safe import, clear error on deploy path."""
    module = _load_wrapper(monkeypatch, None, "guard")
    assert module.modal_app is None
    assert module.asgi_app is None
    with pytest.raises(RuntimeError, match="modal"):
        module.build_modal_asgi()
