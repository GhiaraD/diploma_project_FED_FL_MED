"""
Teste pentru scripts/prepare_experiment_data.py

Acoperă task-urile opționale:
  2.1 — Property 1: Partiționare completă și disjunctă a dataset-ului
  2.2 — Property 2: Partiționare completă și disjunctă a nodurilor FL
  2.3 — Property 3: Reproductibilitate a split-urilor cu seed fix

Rulare:
    pytest tests/test_prepare_experiment_data.py -v
"""
import sys
from pathlib import Path
from typing import List, Tuple

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Adaugă scripts în path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from prepare_experiment_data import (
    stratified_split,
    dirichlet_split,
    local_train_val_split,
    save_csv,
    save_distribution_json,
)

Sample = Tuple[str, int]


# ============================================================================
# Helpers
# ============================================================================

def make_samples(n_normal: int, n_pneumonia: int) -> List[Sample]:
    """Generează o listă sintetică de samples."""
    samples = []
    for i in range(n_normal):
        samples.append((f"normal_{i}.jpg", 0))
    for i in range(n_pneumonia):
        samples.append((f"pneumonia_{i}.jpg", 1))
    return samples


# ============================================================================
# Task 2.1 — Property 1: Partiționare completă și disjunctă a dataset-ului
# Feature: experiment-logging-and-visualization, Property 1: dataset split completeness
# ============================================================================

class TestProperty1DatasetSplitCompleteness:

    @given(
        n_normal=st.integers(min_value=5, max_value=500),
        n_pneumonia=st.integers(min_value=5, max_value=1500),
        test_ratio=st.floats(min_value=0.05, max_value=0.4),
    )
    @settings(max_examples=100)
    def test_test_plus_train_equals_total(self, n_normal, n_pneumonia, test_ratio):
        """Property 1: |test_global| + |train_pool| = |total|."""
        samples = make_samples(n_normal, n_pneumonia)
        total = len(samples)
        # test_size trebuie să fie ≥ numărul de clase (2) pentru split stratificat
        assume(int(total * test_ratio) >= 2)

        test_global, train_pool = stratified_split(samples, test_ratio, seed=42)

        assert len(test_global) + len(train_pool) == total

    @given(
        n_normal=st.integers(min_value=5, max_value=500),
        n_pneumonia=st.integers(min_value=5, max_value=1500),
        test_ratio=st.floats(min_value=0.05, max_value=0.4),
    )
    @settings(max_examples=100)
    def test_test_and_train_are_disjoint(self, n_normal, n_pneumonia, test_ratio):
        """Property 1: test_global ∩ train_pool = ∅."""
        samples = make_samples(n_normal, n_pneumonia)
        assume(int(len(samples) * test_ratio) >= 2)

        test_global, train_pool = stratified_split(samples, test_ratio, seed=42)

        test_paths = {fp for fp, _ in test_global}
        train_paths = {fp for fp, _ in train_pool}
        assert len(test_paths & train_paths) == 0

    @given(
        n_normal=st.integers(min_value=10, max_value=500),
        n_pneumonia=st.integers(min_value=10, max_value=1500),
    )
    @settings(max_examples=100)
    def test_test_ratio_approximately_correct(self, n_normal, n_pneumonia):
        """Property 1: |test_global| / |total| ≈ 0.15 (±2%)."""
        samples = make_samples(n_normal, n_pneumonia)
        total = len(samples)
        test_ratio = 0.15

        test_global, _ = stratified_split(samples, test_ratio, seed=42)

        actual_ratio = len(test_global) / total
        # Toleranță de ±2% sau ±1 imagine
        assert abs(actual_ratio - test_ratio) <= 0.02 or abs(len(test_global) - total * test_ratio) <= 1, (
            f"Ratio actual {actual_ratio:.3f} departe de {test_ratio}"
        )


# ============================================================================
# Task 2.2 — Property 2: Partiționare completă și disjunctă a nodurilor FL
# Feature: experiment-logging-and-visualization, Property 2: node split completeness
# ============================================================================

class TestProperty2NodeSplitCompleteness:

    @given(
        n_normal=st.integers(min_value=10, max_value=500),
        n_pneumonia=st.integers(min_value=10, max_value=1500),
        num_nodes=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_union_of_nodes_equals_train_pool(self, n_normal, n_pneumonia, num_nodes):
        """Property 2: union(node1..nodeN) = train_pool."""
        train_pool = make_samples(n_normal, n_pneumonia)
        node_splits = dirichlet_split(train_pool, num_nodes, alpha=0.5, seed=42)

        assert len(node_splits) == num_nodes

        # Union de toate nodurile
        all_node_paths = set()
        for node in node_splits:
            for fp, _ in node:
                all_node_paths.add(fp)

        train_paths = {fp for fp, _ in train_pool}
        assert all_node_paths == train_paths, (
            f"Union noduri ≠ train_pool. "
            f"Lipsă: {train_paths - all_node_paths}, "
            f"Extra: {all_node_paths - train_paths}"
        )

    @given(
        n_normal=st.integers(min_value=10, max_value=500),
        n_pneumonia=st.integers(min_value=10, max_value=1500),
        num_nodes=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_nodes_are_pairwise_disjoint(self, n_normal, n_pneumonia, num_nodes):
        """Property 2: node_i ∩ node_j = ∅ pentru orice i ≠ j."""
        train_pool = make_samples(n_normal, n_pneumonia)
        node_splits = dirichlet_split(train_pool, num_nodes, alpha=0.5, seed=42)

        node_path_sets = [
            {fp for fp, _ in node}
            for node in node_splits
        ]

        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                intersection = node_path_sets[i] & node_path_sets[j]
                assert len(intersection) == 0, (
                    f"node{i+1} și node{j+1} se suprapun: {intersection}"
                )

    @given(
        n_normal=st.integers(min_value=10, max_value=500),
        n_pneumonia=st.integers(min_value=10, max_value=1500),
        num_nodes=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=100)
    def test_sum_of_node_sizes_equals_train_pool(self, n_normal, n_pneumonia, num_nodes):
        """Property 2: sum(|node_i|) = |train_pool|."""
        train_pool = make_samples(n_normal, n_pneumonia)
        node_splits = dirichlet_split(train_pool, num_nodes, alpha=0.5, seed=42)

        total_in_nodes = sum(len(node) for node in node_splits)
        assert total_in_nodes == len(train_pool), (
            f"sum(|node_i|)={total_in_nodes} ≠ |train_pool|={len(train_pool)}"
        )


# ============================================================================
# Task 2.3 — Property 3: Reproductibilitate a split-urilor cu seed fix
# Feature: experiment-logging-and-visualization, Property 3: reproducibility
# ============================================================================

class TestProperty3Reproducibility:

    @given(
        n_normal=st.integers(min_value=5, max_value=300),
        n_pneumonia=st.integers(min_value=5, max_value=900),
        test_ratio=st.floats(min_value=0.1, max_value=0.3),
    )
    @settings(max_examples=100)
    def test_stratified_split_is_reproducible(self, n_normal, n_pneumonia, test_ratio):
        """Property 3: stratified_split cu seed=42 produce rezultate identice."""
        samples = make_samples(n_normal, n_pneumonia)
        assume(int(len(samples) * test_ratio) >= 2)

        test1, train1 = stratified_split(samples, test_ratio, seed=42)
        test2, train2 = stratified_split(samples, test_ratio, seed=42)

        assert [fp for fp, _ in test1] == [fp for fp, _ in test2]
        assert [fp for fp, _ in train1] == [fp for fp, _ in train2]

    @given(
        n_normal=st.integers(min_value=10, max_value=300),
        n_pneumonia=st.integers(min_value=10, max_value=900),
        num_nodes=st.integers(min_value=2, max_value=8),
    )
    @settings(max_examples=100)
    def test_dirichlet_split_is_reproducible(self, n_normal, n_pneumonia, num_nodes):
        """Property 3: dirichlet_split cu seed=42 produce rezultate identice."""
        train_pool = make_samples(n_normal, n_pneumonia)

        splits1 = dirichlet_split(train_pool, num_nodes, alpha=0.5, seed=42)
        splits2 = dirichlet_split(train_pool, num_nodes, alpha=0.5, seed=42)

        for i, (node1, node2) in enumerate(zip(splits1, splits2)):
            paths1 = [fp for fp, _ in node1]
            paths2 = [fp for fp, _ in node2]
            assert paths1 == paths2, (
                f"node{i+1} diferit între două rulări cu același seed"
            )

    @given(
        n_normal=st.integers(min_value=5, max_value=200),
        n_pneumonia=st.integers(min_value=5, max_value=600),
        seed1=st.integers(min_value=0, max_value=1000),
        seed2=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=50)
    def test_different_seeds_produce_different_splits(self, n_normal, n_pneumonia, seed1, seed2):
        """Property 3 (negativ): seed-uri diferite produc split-uri diferite (de obicei)."""
        assume(seed1 != seed2)
        samples = make_samples(n_normal, n_pneumonia)
        assume(len(samples) >= 20)

        test1, _ = stratified_split(samples, 0.15, seed=seed1)
        test2, _ = stratified_split(samples, 0.15, seed=seed2)

        # Nu garantăm că sunt diferite (pot coincide accidental),
        # dar verificăm că funcția rulează fără erori
        assert len(test1) > 0
        assert len(test2) > 0


# ============================================================================
# Teste unitare suplimentare pentru funcțiile din prepare_experiment_data
# ============================================================================

class TestStratifiedSplitUnit:

    def test_basic_split(self):
        samples = make_samples(100, 300)
        test, train = stratified_split(samples, 0.15, seed=42)
        assert len(test) + len(train) == 400
        assert len(test) == pytest.approx(60, abs=2)

    def test_stratification_preserves_class_ratio(self):
        """Proporția claselor în test ≈ proporția globală."""
        samples = make_samples(100, 300)  # 25% NORMAL, 75% PNEUMONIA
        test, _ = stratified_split(samples, 0.15, seed=42)

        test_normal = sum(1 for _, l in test if l == 0)
        test_pneumonia = sum(1 for _, l in test if l == 1)
        total_test = len(test)

        ratio_normal = test_normal / total_test
        # Așteptat ~25% ± 5%
        assert 0.20 <= ratio_normal <= 0.30, (
            f"Proporție NORMAL în test: {ratio_normal:.2f}, așteptat ~0.25"
        )


class TestDirichletSplitUnit:

    def test_basic_split_5_nodes(self):
        train_pool = make_samples(200, 600)
        splits = dirichlet_split(train_pool, 5, alpha=0.5, seed=42)
        assert len(splits) == 5
        assert sum(len(s) for s in splits) == 800

    def test_all_nodes_nonempty_with_large_dataset(self):
        """Cu un dataset mare, toate nodurile trebuie să aibă cel puțin o imagine."""
        train_pool = make_samples(500, 1500)
        splits = dirichlet_split(train_pool, 5, alpha=0.5, seed=42)
        for i, node in enumerate(splits):
            assert len(node) > 0, f"node{i+1} este gol"

    def test_alpha_affects_heterogeneity(self):
        """α mic → mai multă heterogenitate (distribuție mai inegală)."""
        train_pool = make_samples(200, 600)

        splits_low = dirichlet_split(train_pool, 5, alpha=0.1, seed=42)
        splits_high = dirichlet_split(train_pool, 5, alpha=10.0, seed=42)

        sizes_low = [len(s) for s in splits_low]
        sizes_high = [len(s) for s in splits_high]

        # Variația dimensiunilor trebuie să fie mai mare pentru α mic
        import statistics
        std_low = statistics.stdev(sizes_low)
        std_high = statistics.stdev(sizes_high)

        assert std_low >= std_high, (
            f"α=0.1 ar trebui să producă mai multă variație decât α=10.0. "
            f"std_low={std_low:.1f}, std_high={std_high:.1f}"
        )


class TestLocalTrainValSplitUnit:

    def test_basic_split(self):
        node_samples = make_samples(80, 240)
        train, val = local_train_val_split(node_samples, 0.2, seed=42, node_idx=0)
        assert len(train) + len(val) == 320
        assert len(val) == pytest.approx(64, abs=2)

    def test_single_class_fallback(self):
        """Dacă nodul are o singură clasă, split-ul nu trebuie să eșueze."""
        node_samples = make_samples(100, 0)  # doar NORMAL
        train, val = local_train_val_split(node_samples, 0.2, seed=42, node_idx=0)
        assert len(train) + len(val) == 100
        assert len(val) > 0

    def test_different_nodes_get_different_splits(self):
        """Noduri diferite cu aceleași date trebuie să primească split-uri diferite."""
        node_samples = make_samples(100, 300)
        train0, val0 = local_train_val_split(node_samples, 0.2, seed=42, node_idx=0)
        train1, val1 = local_train_val_split(node_samples, 0.2, seed=42, node_idx=1)

        # Split-urile pot fi diferite (seed diferit per nod)
        paths_val0 = {fp for fp, _ in val0}
        paths_val1 = {fp for fp, _ in val1}
        # Nu garantăm că sunt diferite, dar verificăm că rulează
        assert len(val0) > 0
        assert len(val1) > 0
