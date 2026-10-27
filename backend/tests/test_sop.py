"""SOP import tests (M5): unsaved drafts, the 422 path, retry behavior.

Run: cd backend && .venv/bin/python -m pytest -q
"""

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import app.main as main_module
from app.adapters.base import AdapterNotConfiguredError
from app.adapters.muse_spark import JudgeValidationError, MuseSparkJudge
from app.config import settings
from app.main import app
from app.schemas import ProductProfile

client = TestClient(app)

IMAGE_W, IMAGE_H = 40, 30
SOP = (
    "Bottle inspection: FAIL a bottle with any scratch longer than 5mm "
    "or any contamination stain; PASS otherwise."
)
CATEGORY = "bottle"

DRAFT = {
    "id": "bottle",
    "name": "bottle",
    "defect_prompts": ["scratch", "contamination stain"],
    "rules": SOP,
    "mm_per_px": None,
    "min_score": 0.3,
    "reference_image": None,
}


@pytest.fixture
def image() -> Image.Image:
    return Image.new("RGB", (IMAGE_W, IMAGE_H), color=(120, 120, 120))


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "meta_api_key", "test-key")
    monkeypatch.setattr(settings, "meta_api_base_url", "https://meta.test")
    monkeypatch.setattr(settings, "judge_model_id", "judge-test-id")
    yield


@pytest.fixture
def empty_settings(monkeypatch: pytest.MonkeyPatch):
    for field in ("meta_api_key", "meta_api_base_url", "judge_model_id"):
        monkeypatch.setattr(settings, field, "")
    yield


@pytest.fixture
def no_http(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []

    def _forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("HTTP must not be called")

    monkeypatch.setattr(httpx, "post", _forbidden)
    return calls


class StubSopJudge:
    """Fixed draft so the endpoint test never touches the network."""

    def __init__(self, draft: dict | None = None) -> None:
        self._draft = draft if draft is not None else DRAFT
        self.calls = 0

    def sop_to_profile(self, sop_text: str, category_name: str) -> ProductProfile:
        self.calls += 1
        return ProductProfile.model_validate(self._draft)


class AlwaysInvalidJudge:
    """Every attempt fails validation: the endpoint must answer 422."""

    def __init__(self) -> None:
        self.calls = 0

    def sop_to_profile(self, sop_text: str, category_name: str):
        self.calls += 1
        raise JudgeValidationError("sop_to_profile output failed validation twice")


def _use_stub(stub, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main_module, "_get_sop_judge", lambda: stub)


def test_from_sop_returns_valid_draft_and_saves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubSopJudge()
    _use_stub(stub, monkeypatch)
    resp = client.post(
        "/api/profiles/from-sop", json={"sop_text": SOP, "category_name": CATEGORY}
    )
    assert resp.status_code == 200
    profile = ProductProfile.model_validate(resp.json())
    assert profile.id == "bottle"
    assert profile.defect_prompts == ["scratch", "contamination stain"]
    assert stub.calls == 1


def test_from_sop_saves_nothing_to_profiles_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    profiles_dir = Path("profiles")
    if profiles_dir.is_dir():
        before = {p.name for p in profiles_dir.iterdir()}
    else:
        before = set()
    _use_stub(StubSopJudge(), monkeypatch)
    resp = client.post(
        "/api/profiles/from-sop", json={"sop_text": SOP, "category_name": CATEGORY}
    )
    assert resp.status_code == 200
    if profiles_dir.is_dir():
        assert {p.name for p in profiles_dir.iterdir()} == before


def test_from_sop_garbage_twice_gives_422(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = AlwaysInvalidJudge()
    _use_stub(stub, monkeypatch)
    resp = client.post(
        "/api/profiles/from-sop",
        json={"sop_text": "!!! not a spec !!!", "category_name": "bottle"},
    )
    assert resp.status_code == 422
    assert stub.calls == 1


def test_from_sop_rejects_empty_body() -> None:
    resp = client.post(
        "/api/profiles/from-sop", json={"sop_text": "", "category_name": ""}
    )
    assert resp.status_code == 422


def test_sop_retry_once_then_succeeds(
    configured, no_http, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    valid = dict(DRAFT)

    def _scripted(self, prompt: str):
        calls.append(prompt)
        if len(calls) == 1:
            return {"id": 42}  # fails ProductProfile validation
        return valid

    monkeypatch.setattr(MuseSparkJudge, "_sop_via_meta_api", _scripted)
    profile = MuseSparkJudge().sop_to_profile(SOP, CATEGORY)
    assert profile.id == "bottle"
    assert len(calls) == 2
    assert "failed validation" in calls[1]
    assert no_http == []


def test_sop_double_failure_raises_judge_error(
    configured, no_http, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def _always_invalid(self, prompt: str):
        calls.append(prompt)
        return {"id": 42}

    monkeypatch.setattr(MuseSparkJudge, "_sop_via_meta_api", _always_invalid)
    with pytest.raises(JudgeValidationError):
        MuseSparkJudge().sop_to_profile("!!! not a spec !!!", CATEGORY)
    assert len(calls) == 2
    assert no_http == []


def test_sop_unconfigured_adapter_errors_without_network(
    empty_settings, no_http
) -> None:
    with pytest.raises(AdapterNotConfiguredError):
        MuseSparkJudge().sop_to_profile(SOP, CATEGORY)
    assert no_http == []
