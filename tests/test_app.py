import pytest
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def test_demo_flow_all_pages_and_languages(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "app.db"))
    at = AppTest.from_file("dashboard/app.py", default_timeout=60).run()
    assert not at.exception
    next(b for b in at.button if "▶" in b.label).click(); at.run()
    assert not at.exception
    for lang in ("ta", "hi", "ml", "en"):
        at.selectbox(key="lang_sel").select(lang).run()
        for page in ("overview", "findings", "forecast", "fix", "audit", "settings"):
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception, (lang, page)


def test_wizard_steps(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "w.db"))
    at = AppTest.from_file("dashboard/app.py", default_timeout=60).run()
    next(b for b in at.button if "Next" in b.label).click(); at.run()
    assert not at.exception and any("Test connection" in b.label for b in at.button)
    next(b for b in at.button if "Test connection" in b.label).click(); at.run()
    assert not at.exception and at.error          # no credentials -> friendly error, no crash


def test_demo_only_hides_connect(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "d.db"))
    monkeypatch.setenv("BILLSHIELD_DEMO_ONLY", "true")
    at = AppTest.from_file("dashboard/app.py", default_timeout=60).run()
    assert not at.exception
    assert not any("Next" in b.label for b in at.button) and any("▶" in b.label for b in at.button)
