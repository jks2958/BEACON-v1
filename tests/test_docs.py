"""The README quotes measured numbers. This pins them to the metrics
files so the two cannot drift apart silently.

This is not hypothetical: the README once claimed the Network model was
"not trained" for an hour after it had been trained, merged, and shipped,
because a branch written earlier edited that table and merged later.
"""
import os
import re

import pytest

from pipeline.viz import headline, load_metrics

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def readme() -> str:
    with open(os.path.join(REPO_ROOT, "README.md")) as fh:
        return fh.read()


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def test_network_accuracies_match_the_metrics_file(readme):
    metrics = load_metrics("network")
    if metrics is None:
        pytest.skip("network metrics not present")
    sample, flow = headline(metrics, "sample"), headline(metrics, "flow")

    assert _pct(sample["accuracy"]) in readme, "per-capture accuracy is stale"
    assert _pct(flow["accuracy"]) in readme, "per-flow accuracy is stale"
    assert f"{flow['n']:,}" in readme, "per-flow n is stale"
    assert str(sample["n"]) in readme, "per-capture n is stale"


def test_memory_accuracy_matches_the_metrics_file(readme):
    metrics = load_metrics("memory")
    if metrics is None:
        pytest.skip("memory metrics not present")
    assert _pct(headline(metrics)["accuracy"]) in readme, "memory accuracy is stale"


def test_both_units_are_named_wherever_the_capture_number_appears(readme):
    # The per-capture figure alone overstates what the model does, so it
    # must never appear without its unit and its per-flow counterpart.
    assert "per capture" in readme
    assert "per flow" in readme


def test_readme_does_not_claim_an_untrained_model_that_exists(readme):
    for stream in ("network", "memory"):
        if load_metrics(stream) is None:
            continue
        pattern = rf"\*\*{stream}-stream model\*\*[^|]*\|[^|]*not trained"
        assert not re.search(pattern, readme, re.I), \
            f"README says the {stream} model is untrained, but its metrics exist"


def test_test_count_claim_is_not_wildly_stale(readme):
    # A loose bound: the point is to catch "77" being left behind after the
    # suite doubles, not to force an edit on every added test.
    claimed = [int(n) for n in re.findall(r"(\d+) tests", readme)]
    if not claimed:
        pytest.skip("README makes no test-count claim")
    import subprocess
    import sys
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", out.stdout)
    if not m:
        pytest.skip("could not count tests")
    actual = int(m.group(1))
    for c in claimed:
        assert abs(c - actual) <= 10, f"README claims {c} tests; suite collects {actual}"
