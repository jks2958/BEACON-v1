from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parents[1]


def run_page(relative):
    app = AppTest.from_file(ROOT / relative, default_timeout=30).run()
    assert not app.exception
    return app


def test_general_home_has_clear_ctas_support_and_future_boundary():
    app = run_page("pages/general_home.py")
    buttons = {button.label for button in app.button}
    assert {"Analyze Evidence", "Switch to Analyst Mode"} <= buttons
    assert any("Prepared Network CSV" in item.value for item in app.success)
    assert any("diagnostic-only" in item.value for item in app.info)


def test_general_analyze_is_a_guided_accessible_workflow():
    app = run_page("pages/general_analyze.py")
    assert app.radio[0].label == "Evidence type"
    assert app.file_uploader[0].label == "Upload prepared network telemetry"
    assert app.button[0].label == "Analyze Evidence"
    assert app.button[0].disabled


def test_all_analyst_pages_have_polished_empty_or_initial_state():
    for page in ["pages/0_Dashboard.py", "pages/1_Network_Detection.py",
                 "pages/2_Memory_Detection.py", "pages/3_Explainability.py",
                 "pages/4_Methodology.py", "pages/about_beacon.py"]:
        app = run_page(page)
        assert not app.exception


def test_explainability_empty_state_is_explicit():
    run_page("pages/3_Explainability.py")
    assert "Run an analysis first" in (ROOT / "pages/3_Explainability.py").read_text()


def test_network_pcap_boundary_is_visually_explicit():
    app = run_page("pages/1_Network_Detection.py")
    assert any("diagnostic-only" in item.value for item in app.info)


def test_responsive_and_accessible_design_rules_are_shared():
    source = (ROOT / "pipeline/ui.py").read_text()
    assert "@media (max-width: 900px)" in source
    assert 'role="status"' in source
    assert 'aria-label="Current mode:' in source
