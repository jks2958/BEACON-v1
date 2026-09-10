"""SHAP-based per-prediction explanations, shared by both classifiers."""
from __future__ import annotations

import pandas as pd
import shap


class Explainer:
    """Wraps a SHAP TreeExplainer bound to one trained MalwareClassifier.
    TreeExplainer is used (rather than a model-agnostic explainer)
    because it computes exact Shapley values for tree ensembles in
    polynomial rather than exponential time — the only practical choice
    at this row count.
    """

    def __init__(self, classifier):
        self.classifier = classifier
        self.tree_explainer = shap.TreeExplainer(classifier.model)

    def explain(self, row: pd.DataFrame):
        """Return SHAP values for a single preprocessed, feature-aligned
        row (a 1-row DataFrame with columns == classifier.feature_order).
        For a multiclass model this is one array of shape
        (n_features, n_classes)."""
        aligned = row[self.classifier.feature_order]
        return self.tree_explainer.shap_values(aligned)

    def top_features(self, row: pd.DataFrame, predicted_class_idx: int, n: int = 5) -> pd.DataFrame:
        """Return the n features with the largest absolute SHAP value
        for the predicted class, as a small DataFrame an analyst can
        read directly (feature name, value, SHAP contribution)."""
        shap_values = self.explain(row)

        # shap_values shape depends on version/model: either a list of
        # per-class arrays, or one (n_rows, n_features, n_classes) array.
        if isinstance(shap_values, list):
            class_shap = shap_values[predicted_class_idx][0]
        elif shap_values.ndim == 3:
            class_shap = shap_values[0, :, predicted_class_idx]
        else:
            class_shap = shap_values[0]

        feature_names = self.classifier.feature_order
        feature_values = row[feature_names].iloc[0].values

        result = pd.DataFrame(
            {
                "feature": feature_names,
                "value": feature_values,
                "shap_value": class_shap,
            }
        )
        result["abs_shap"] = result["shap_value"].abs()
        return result.sort_values("abs_shap", ascending=False).head(n).drop(columns="abs_shap")
