"""encode_handshake and the DERIVATIONS registry.

This step runs BEFORE the Preprocessor and creates columns it was fitted
on. It lived only in the training script until it was found that the
Network page rejected every real capture, so these tests pin the contract
both sides depend on.
"""
import numpy as np
import pandas as pd

from pipeline.common import (DERIVATIONS, INCOMPLETE_HANDSHAKE, encode_handshake)


def test_incomplete_handshake_string_becomes_indicator_and_sentinel():
    df = pd.DataFrame({"delta_start": [INCOMPLETE_HANDSHAKE, "0.25"],
                       "handshake_duration": ["0.5", INCOMPLETE_HANDSHAKE]})
    out = encode_handshake(df)

    assert list(out["delta_start_incomplete"]) == [1, 0]
    assert list(out["handshake_duration_incomplete"]) == [0, 1]
    # -1 is a sentinel: every real duration is >= 0, so the model can
    # separate "never completed" from "completed instantly".
    assert out["delta_start"].iloc[0] == -1.0
    assert out["delta_start"].iloc[1] == 0.25
    assert out["handshake_duration"].iloc[1] == -1.0


def test_surrounding_whitespace_still_counts_as_incomplete():
    out = encode_handshake(pd.DataFrame({"delta_start": [f"  {INCOMPLETE_HANDSHAKE} "]}))
    assert out["delta_start_incomplete"].iloc[0] == 1


def test_columns_become_numeric_not_object():
    out = encode_handshake(pd.DataFrame({"delta_start": [INCOMPLETE_HANDSHAKE, "0.25"]}))
    assert out["delta_start"].dtype == np.float32


def test_unparseable_value_is_nan_but_not_flagged_incomplete():
    # Garbage is missing data for Step 4 to fill; it is NOT the
    # behavioural "handshake never completed" signal.
    out = encode_handshake(pd.DataFrame({"delta_start": ["garbage"]}))
    assert out["delta_start_incomplete"].iloc[0] == 0
    assert pd.isna(out["delta_start"].iloc[0])


def test_missing_handshake_columns_are_tolerated():
    df = pd.DataFrame({"unrelated": [1]})
    out = encode_handshake(df)
    assert list(out.columns) == ["unrelated"]


def test_input_frame_is_not_mutated():
    df = pd.DataFrame({"delta_start": [INCOMPLETE_HANDSHAKE]})
    encode_handshake(df)
    assert df["delta_start"].iloc[0] == INCOMPLETE_HANDSHAKE
    assert "delta_start_incomplete" not in df.columns


def test_already_numeric_input_is_unchanged():
    # An upload that has been through the derivation once (or a CSV
    # exported post-encoding) must survive a second pass.
    once = encode_handshake(pd.DataFrame({"delta_start": [INCOMPLETE_HANDSHAKE, "0.25"]}))
    twice = encode_handshake(once)
    assert list(twice["delta_start"]) == list(once["delta_start"])
    assert list(twice["delta_start_incomplete"]) == [1, 0]


def test_registry_maps_the_name_training_records():
    # train_network.py writes "encode_handshake" into the artifact bundle;
    # the controller looks it up here. A rename that breaks this pairing
    # would silently make every saved model unloadable.
    assert DERIVATIONS["encode_handshake"] is encode_handshake
