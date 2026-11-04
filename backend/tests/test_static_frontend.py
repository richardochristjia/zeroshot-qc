import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture
def web(tmp_path, monkeypatch):
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>spa</html>")
    (root / "assets" / "x.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("TOPSECRET")
    monkeypatch.setattr(settings, "frontend_dir", str(root))
    return root


@pytest.mark.parametrize("path", ["/", "/eval"])
def test_spa_routes_return_index(web, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "spa" in r.text


def test_asset_served(web):
    r = client.get("/assets/x.js")
    assert r.status_code == 200
    assert r.text == "console.log(1)"


def test_api_untouched(web):
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "path", ["/assets/../../secret.txt", "/..%2Fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2F..%2Fsecret.txt"]
)
def test_traversal_never_leaks(web, path):
    assert "TOPSECRET" not in client.get(path).text


def test_unset_dir_is_404(monkeypatch):
    monkeypatch.setattr(settings, "frontend_dir", "")
    assert client.get("/").status_code == 404
