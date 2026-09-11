"""Class-imbalance handling for BEACON's training pipelines.

Two strategies, matched to how severe the imbalance actually is (see the
project report, Ch. 3): SmoteResampler for the Network stream's moderate
imbalance, ClusterBasedResampler (CSBBoost-style) for the Memory stream's
severely underrepresented Exploit class, where plain SMOTE would
interpolate too many synthetic points from too few real ones.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors


class Resampler:
    """Shared constructor only -- deliberately not an ABC with an
    abstract `resample`. SmoteResampler.resample(X, y) rebalances every
    class; ClusterBasedResampler.resample(X, y, minority_label) targets
    one named minority class and returns a 3-tuple (X, y, is_synthetic)
    instead of 2. Those signatures can't share one contract, and both
    training scripts call each resampler by its concrete class, never
    through this base type -- so there is no polymorphic call site for
    a shared abstract method to serve, only a foot-gun for code that
    might later try `resampler.resample(X, y)` generically."""

    def __init__(self, k_neighbors: int = 5, random_state: int = 42):
        self.k_neighbors = k_neighbors
        self.random_state = random_state


class SmoteResampler(Resampler):
    """Standard multiclass SMOTE — used for the Network stream's
    moderate (~5:1) imbalance."""

    def resample(self, X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        smote = SMOTE(random_state=self.random_state, k_neighbors=self.k_neighbors)
        X_res, y_res = smote.fit_resample(X, y)
        return X_res, y_res


class ClusterBasedResampler(Resampler):
    """CSBBoost-style resampling for one severely imbalanced class: the
    minority class is clustered first, then SMOTE-interpolated
    proportionally within each cluster, so a handful of real points
    don't get flattened into one undifferentiated blob of synthetic
    duplicates (Salehi & Khedmati, 2024)."""

    def __init__(self, k_range: range = range(2, 5), k_neighbors: int = 3, random_state: int = 42):
        super().__init__(k_neighbors=k_neighbors, random_state=random_state)
        self.k_range = k_range
        self.chosen_k: int | None = None
        self.chosen_silhouette: float | None = None

    def best_k_by_silhouette(self, X: np.ndarray) -> int:
        best_k, best_score = None, -1.0
        max_k = min(max(self.k_range), len(X) - 1)
        for k in [k for k in self.k_range if k <= max_k]:
            labels = KMeans(n_clusters=k, random_state=self.random_state, n_init=10).fit_predict(X)
            score = silhouette_score(X, labels)
            if score > best_score:
                best_k, best_score = k, score
        self.chosen_k, self.chosen_silhouette = best_k, best_score
        return best_k

    def _smote_within_cluster(self, X_cluster: np.ndarray, n_synthetic: int) -> np.ndarray:
        rng = np.random.default_rng(self.random_state)
        n_samples = X_cluster.shape[0]
        k = min(self.k_neighbors, n_samples - 1)

        if k < 1:
            idx = rng.integers(0, n_samples, size=n_synthetic)
            return X_cluster[idx]

        nn = NearestNeighbors(n_neighbors=k + 1).fit(X_cluster)
        _, neighbor_idx = nn.kneighbors(X_cluster)

        synthetic = np.zeros((n_synthetic, X_cluster.shape[1]))
        for s in range(n_synthetic):
            i = rng.integers(0, n_samples)
            neighbor_choices = neighbor_idx[i][1:]
            j = rng.choice(neighbor_choices)
            lam = rng.random()
            synthetic[s] = X_cluster[i] + lam * (X_cluster[j] - X_cluster[i])
        return synthetic

    def resample(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        minority_label,
        target_total: int | None = None,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Resample only `minority_label`'s rows, leaving every other
        class untouched. Returns (X_resampled, y_resampled,
        is_synthetic) so callers can carry the synthetic flag forward
        (per the report's own caveat about Exploit's lower-confidence
        evaluation)."""
        minority_mask = y == minority_label
        X_minority = X[minority_mask].reset_index(drop=True)
        X_other = X[~minority_mask].reset_index(drop=True)
        y_other = y[~minority_mask].reset_index(drop=True)

        if target_total is None:
            target_total = int(y[~minority_mask].value_counts().min())

        n_needed = max(0, target_total - len(X_minority))
        X_min_values = X_minority.values

        is_synthetic_minority = np.zeros(len(X_minority), dtype="int8")

        if n_needed > 0 and len(X_minority) >= 2:
            k = self.best_k_by_silhouette(X_min_values)
            synthetic_chunks = []

            if k is None:
                # The minority class is too small for k_range's smallest
                # candidate (e.g. fewer than 3 real rows) -- there's no
                # meaningful cluster structure to find, so interpolate
                # across the whole minority class as one group instead
                # of crashing KMeans(n_clusters=None).
                synthetic_chunks.append(self._smote_within_cluster(X_min_values, n_needed))
            else:
                cluster_labels = KMeans(
                    n_clusters=k, random_state=self.random_state, n_init=10
                ).fit_predict(X_min_values)

                for c in range(k):
                    cluster_mask = cluster_labels == c
                    cluster_data = X_min_values[cluster_mask]
                    proportion = cluster_mask.sum() / len(X_min_values)
                    n_for_cluster = int(round(n_needed * proportion))
                    if n_for_cluster == 0 or len(cluster_data) == 0:
                        continue
                    synthetic_chunks.append(self._smote_within_cluster(cluster_data, n_for_cluster))

            if synthetic_chunks:
                synthetic_values = np.concatenate(synthetic_chunks, axis=0)
                synthetic_df = pd.DataFrame(synthetic_values, columns=X_minority.columns)
                X_minority = pd.concat([X_minority, synthetic_df], ignore_index=True)
                is_synthetic_minority = np.concatenate(
                    [is_synthetic_minority, np.ones(len(synthetic_df), dtype="int8")]
                )

        y_minority = pd.Series([minority_label] * len(X_minority))
        is_synthetic_other = np.zeros(len(X_other), dtype="int8")

        X_resampled = pd.concat([X_minority, X_other], ignore_index=True)
        y_resampled = pd.concat([y_minority, y_other], ignore_index=True)
        is_synthetic = pd.Series(np.concatenate([is_synthetic_minority, is_synthetic_other]))

        return X_resampled, y_resampled, is_synthetic
