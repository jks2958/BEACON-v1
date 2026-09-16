import pandas as pd
import pytest

from pipeline.interpretation import (CATEGORY_KNOWLEDGE, InterpretationError,
                                     ReviewStatus, interpret_analysis)


CATEGORIES = {"Backdoor", "Benign", "Exploit", "HackTool", "Hoax",
              "Rootkit", "Trojan", "Virus", "Worm"}


def result(category="Backdoor", confidence=0.78, features=None):
    return {
        "verdict": category,
        "confidence": confidence,
        "top_features": features if features is not None else pd.DataFrame([
            {"feature": "packets_IAT_mean", "value": 0.4, "shap_value": 0.8},
            {"feature": "total_payload_bytes", "value": 0.7, "shap_value": 0.5},
            {"feature": "opaque_feature", "value": 2.0, "shap_value": -0.3},
        ]),
    }


def test_all_nine_categories_have_complete_deterministic_knowledge():
    assert set(CATEGORY_KNOWLEDGE) == CATEGORIES
    for category, entry in CATEGORY_KNOWLEDGE.items():
        assert entry.display_name and entry.description and entry.risk_explanation
        assert entry.actions
        assert interpret_analysis(result(category), "network") == \
            interpret_analysis(result(category), "network")


def test_interpretation_preserves_numeric_confidence_without_unvalidated_label():
    interpreted = interpret_analysis(result(confidence=0.781234), "network")
    assert interpreted.confidence_value == 0.781234
    assert interpreted.confidence_label is None
    assert interpreted.review_status is ReviewStatus.RESULT_AVAILABLE
    assert interpreted.review_threshold_active is False
    assert "Needs Review is not activated" in interpreted.limitations[1]


def test_shap_evidence_keeps_feature_value_direction_and_strength_order():
    interpreted = interpret_analysis(result(), "network")
    first, second, third = interpreted.evidence_items
    assert [item.feature_name for item in interpreted.evidence_items] == [
        "packets_IAT_mean", "total_payload_bytes", "opaque_feature"]
    assert first.feature_value == 0.4 and first.shap_value == 0.8
    assert first.direction == "toward" and first.evidence_strength == "strongest"
    assert second.display_name == "Traffic volume pattern"
    assert third.direction == "away"
    assert "reduced support" in third.human_explanation


def test_unknown_feature_uses_conservative_fallback_without_behavior_claim():
    features = pd.DataFrame([
        {"feature": "totally_unknown", "value": 9, "shap_value": 1.0},
    ])
    item = interpret_analysis(result(features=features), "memory").evidence_items[0]
    assert item.display_name == "Behavioral measurement"
    assert item.feature_name == "totally_unknown"
    assert "behavioral characteristic" in item.human_explanation
    forbidden = ("command-and-control", "stole", "password", "attacker")
    assert not any(word in item.human_explanation.lower() for word in forbidden)


def test_memory_interpretation_includes_stream_specific_caution():
    interpreted = interpret_analysis(result("Trojan"), "memory")
    assert any("Memory-based family classification is less reliable" in note
               for note in interpreted.limitations)
    assert interpreted.short_summary == "The model classified this memory telemetry as Trojan."


def test_recommendations_are_precautionary_and_never_automated_or_destructive():
    forbidden = ("delete", "terminate", "disable service", "automatically", "confirmed infection")
    for category in CATEGORIES:
        actions = " ".join(interpret_analysis(result(category), "network").recommended_actions).lower()
        assert not any(term in actions for term in forbidden)


def test_interpretation_requires_real_model_result_and_shap_evidence():
    with pytest.raises(InterpretationError, match="completed model result"):
        interpret_analysis({}, "network")
    with pytest.raises(InterpretationError, match="lacks confidence or SHAP"):
        interpret_analysis({"verdict": "Backdoor"}, "network")


def test_pcap_diagnostic_without_verdict_cannot_create_public_interpretation():
    diagnostic_only = {"packet_count": 12, "compatibility_status": "partially_compatible"}
    with pytest.raises(InterpretationError, match="completed model result"):
        interpret_analysis(diagnostic_only, "network")


def test_bad_shap_shape_and_unknown_category_fail_closed():
    with pytest.raises(InterpretationError, match="missing required fields"):
        interpret_analysis(result(features=pd.DataFrame({"feature": ["x"]})), "network")
    with pytest.raises(InterpretationError, match="Unsupported malware category"):
        interpret_analysis(result(category="Unknown"), "network")
