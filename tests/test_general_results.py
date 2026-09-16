from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from pipeline.app_state import ACTIVE_STREAM_KEY, RESULTS_KEY
from pipeline.application import AnalysisOutput


APP = Path(__file__).parents[1] / "app.py"


def completed_output(stream="memory"):
    result = {
        "verdict": "Trojan",
        "confidence": 0.73125,
        "n_rows": 1,
        "aggregate_probabilities": pd.Series(
            {"Backdoor": 0.1, "Benign": 0.16875, "Trojan": 0.73125}
        ),
        "top_features": pd.DataFrame([
            {"feature": "pslist.nproc", "value": 42.0, "shap_value": 0.8},
            {"feature": "dlllist.ndlls", "value": 18.0, "shap_value": 0.4},
            {"feature": "unknown_metric", "value": 3.0, "shap_value": -0.2},
        ]),
    }
    return AnalysisOutput(stream, pd.DataFrame({"pslist.nproc": [42]}), result)


def test_general_results_renders_grounded_interpretation_without_inference():
    app = AppTest.from_file(APP, default_timeout=30).run()
    output = completed_output()
    app.session_state[RESULTS_KEY] = {"memory": output}
    app.session_state[ACTIVE_STREAM_KEY] = "memory"
    app.switch_page("pages/general_results.py").run()

    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    captions = " ".join(item.value for item in app.caption)
    assert "Malware disguised as legitimate software" in text
    assert "Process activity pattern" in text
    assert "Loaded-code pattern" in text
    assert "Run a scan with trusted" in text
    assert "Memory-based family classification is less reliable" in captions
    assert app.metric[0].value == "Trojan"
    assert app.metric[1].value == "73.1%"
    assert app.metric[2].value == "Result available"
    assert app.session_state[RESULTS_KEY]["memory"] is output


def test_general_results_without_analysis_remains_non_diagnostic():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.switch_page("pages/general_results.py").run()
    assert not app.exception
    assert any("No analysis yet" in item.value for item in app.info)
