from pathlib import Path

from streamlit.testing.v1 import AppTest

import pipeline.application as application


APP = Path(__file__).parents[1] / "app.py"
UPLOAD_PAGES = [
    "pages/general_analyze.py", "pages/0_Dashboard.py",
    "pages/1_Network_Detection.py", "pages/2_Memory_Detection.py",
]


def test_general_mode_is_default_and_switches_to_analyst_dashboard():
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.segmented_control(key="beacon_mode").value == "General"
    assert any(button.label == "Analyze Evidence" for button in app.button)

    app.segmented_control(key="beacon_mode").set_value("Analyst").run()
    assert not app.exception
    assert app.file_uploader


def test_general_home_loads_no_model_and_analyst_cache_creates_only_one(monkeypatch):
    calls = []

    class StubController:
        def __init__(self, stream):
            calls.append(stream)

    application.get_controller.clear()
    monkeypatch.setattr(application, "DashboardController", StubController)
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert calls == []

    app.segmented_control(key="beacon_mode").set_value("Analyst").run()
    assert not app.exception
    assert calls == ["network"]

    app.run()
    assert calls == ["network"]
    application.get_controller.clear()


def test_every_upload_page_uses_the_shared_ingestion_entry_point():
    root = APP.parent
    for relative in UPLOAD_PAGES:
        source = (root / relative).read_text()
        assert "analyze_upload(" in source
        assert "pd.read_csv" not in source
        assert ".handle_upload(" not in source
        assert ".run_pipeline(" not in source
