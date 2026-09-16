"""Strict parity between direct controller and normalized-evidence paths."""
from io import BytesIO

import numpy as np
import pandas as pd
import pytest

from conftest import synth_upload
from pipeline.application import analyze_evidence, get_controller
from pipeline.controller import DashboardController
from pipeline.ingestion import (EvidenceIngestionService, EvidenceType,
                                EvidenceUpload)


def copies(frame, name="evidence.csv"):
    payload = frame.to_csv(index=False).encode()
    direct = BytesIO(payload)
    direct.name = name
    return payload, direct


def full_shap(controller, validated):
    transformed = controller.preprocessor.transform(validated)
    features = transformed[controller.feature_cols]
    return np.asarray(controller.explainer.explain(features.iloc[[0]]))


@pytest.mark.parametrize("stream,evidence_type", [
    ("network", EvidenceType.NETWORK_CSV),
    ("memory", EvidenceType.MEMORY_CSV),
])
def test_ingestion_application_path_is_identical_to_direct_path(stream, evidence_type):
    cached = get_controller(stream)
    direct_controller = DashboardController(stream)
    source = synth_upload(cached, n_rows=4, seed=202)
    payload, direct_file = copies(source)

    direct_frame = direct_controller.handle_upload(direct_file)
    direct = direct_controller.run_pipeline(direct_frame)
    parsed = EvidenceIngestionService().ingest(
        EvidenceUpload("evidence.csv", payload, stream, "text/csv")
    )
    wrapped = analyze_evidence(parsed)

    assert parsed.evidence_type is evidence_type
    assert parsed.stream == wrapped.stream == direct_controller.stream
    assert list(cached.classifier.label_encoder.classes_) == \
        list(direct_controller.classifier.label_encoder.classes_)
    pd.testing.assert_frame_equal(parsed.dataframe, source)
    pd.testing.assert_frame_equal(wrapped.validated_frame, direct_frame, check_exact=True)
    assert wrapped.evidence is parsed
    assert wrapped.result["verdict"] == direct["verdict"]
    assert wrapped.result["n_rows"] == direct["n_rows"]
    np.testing.assert_allclose(wrapped.result["confidence"], direct["confidence"], rtol=0, atol=0)
    np.testing.assert_array_equal(wrapped.result["row_predictions"], direct["row_predictions"])
    pd.testing.assert_series_equal(
        wrapped.result["aggregate_probabilities"], direct["aggregate_probabilities"],
        check_exact=True,
    )
    pd.testing.assert_frame_equal(
        wrapped.result["probabilities"], direct["probabilities"], check_exact=True,
    )
    pd.testing.assert_frame_equal(
        wrapped.result["top_features"].reset_index(drop=True),
        direct["top_features"].reset_index(drop=True), check_exact=True,
    )
    np.testing.assert_allclose(
        full_shap(cached, wrapped.validated_frame),
        full_shap(direct_controller, direct_frame), rtol=0, atol=0,
    )


@pytest.mark.parametrize("stream", ["network", "memory"])
def test_scientific_schema_error_passes_through_ingestion_unchanged(stream):
    controller = get_controller(stream)
    malformed = synth_upload(controller).drop(columns=controller.feature_cols[:2])
    payload, direct_file = copies(malformed)
    parsed = EvidenceIngestionService().ingest(
        EvidenceUpload("malformed.csv", payload, stream)
    )

    with pytest.raises(ValueError) as direct_error:
        controller.handle_upload(direct_file)
    with pytest.raises(ValueError) as ingested_error:
        analyze_evidence(parsed)
    assert type(ingested_error.value) is type(direct_error.value)
    assert str(ingested_error.value) == str(direct_error.value)
