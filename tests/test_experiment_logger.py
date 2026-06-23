"""
Teste unitare pentru ExperimentLogger.

Acoperă task-urile opționale:
  1.1 — teste unitare
  1.2 — Property 4: Round-trip CSV
  1.3 — Property 6: Structura run_config.json
  1.4 — Property 7: Selecția best round
  1.5 — Property 8: Structura predictions_test.csv
  1.6 — Property 9: Corectitudinea confusion_matrix.json
  1.7 — Property 10: Integritatea hash-ului modelului
  1.8 — Property 11: Header CSV scris o singură dată

Rulare:
    pytest tests/test_experiment_logger.py -v
"""
import csv
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

import numpy as np
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Import direct din fișier, ocolind __init__.py care importă flwr
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "experiment_logger",
    Path(__file__).parent.parent
    / "shared" / "python" / "node_core" / "node_core" / "experiment_logger.py",
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ExperimentLogger = _mod.ExperimentLogger
EpochMetrics = _mod.EpochMetrics
RoundMetrics = _mod.RoundMetrics
NodeRoundMetrics = _mod.NodeRoundMetrics
_append_csv = _mod._append_csv


# ============================================================================
# Helpers
# ============================================================================

def make_epoch_metrics(epoch: int = 1) -> EpochMetrics:
    return EpochMetrics(
        epoch=epoch,
        train_loss=0.45,
        val_loss=0.38,
        val_auc=0.89,
        val_f1=0.87,
        val_sensitivity=0.91,
        val_specificity=0.78,
        val_pr_auc=0.90,
        lr=0.0001,
        time_epoch_sec=45.3,
    )


def make_round_metrics(round_num: int = 1, test_auc: float = 0.87, test_f2: float = 0.85) -> RoundMetrics:
    return RoundMetrics(
        round=round_num,
        num_clients=5,
        aggregation_method="fedavg",
        time_round_sec=123.4,
        update_norm=0.023,
        test_loss=0.12,
        test_auc=test_auc,
        test_f1=0.85,
        test_f2=test_f2,
        test_sensitivity=0.90,
        test_specificity=0.76,
        test_pr_auc=0.89,
    )


def make_node_metrics(round_num: int = 1, node_id: str = "node1") -> NodeRoundMetrics:
    return NodeRoundMetrics(
        round=round_num,
        node_id=node_id,
        n_train_samples_used=708,
        val_auc=0.82,
        val_f1=0.80,
        val_f2=0.78,
        val_sensitivity=0.87,
        val_specificity=0.72,
        val_pr_auc=0.84,
        local_train_time_sec=45.2,
        delta_norm=0.012,
    )


# ============================================================================
# Task 1.1 — Teste unitare
# ============================================================================

class TestWriteRunConfig:
    """test_write_run_config_creates_file"""

    def test_creates_file_with_required_fields(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        config = {
            "run_id": "test_run",
            "experiment_type": "centralized",
            "model_arch": "efficientnet_b0",
        }
        logger.write_run_config(config)

        config_path = tmp_path / "run01" / "run_config.json"
        assert config_path.exists(), "run_config.json trebuie să existe"

        with open(config_path) as f:
            saved = json.load(f)

        assert saved["run_id"] == "test_run"
        assert saved["experiment_type"] == "centralized"
        assert "timestamp" in saved, "timestamp trebuie adăugat automat"
        assert "git_commit_hash" in saved, "git_commit_hash trebuie adăugat automat"

    def test_overwrites_existing_file(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.write_run_config({"run_id": "v1"})
        logger.write_run_config({"run_id": "v2"})

        with open(tmp_path / "run01" / "run_config.json") as f:
            saved = json.load(f)
        assert saved["run_id"] == "v2"

    def test_git_hash_is_string(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.write_run_config({"run_id": "x"})
        with open(tmp_path / "run01" / "run_config.json") as f:
            saved = json.load(f)
        assert isinstance(saved["git_commit_hash"], str)


class TestAppendEpochMetrics:
    """test_append_epoch_metrics_creates_header_once"""

    def test_header_written_once_for_n_rows(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        n = 5
        for i in range(1, n + 1):
            logger.append_epoch_metrics(make_epoch_metrics(epoch=i))

        csv_path = tmp_path / "run01" / "metrics_by_epoch.csv"
        assert csv_path.exists()

        with open(csv_path) as f:
            lines = f.readlines()

        # 1 header + n rânduri de date
        assert len(lines) == n + 1, f"Așteptat {n+1} linii, găsit {len(lines)}"

        # Header-ul apare o singură dată
        header_count = sum(1 for l in lines if l.startswith("epoch"))
        assert header_count == 1, "Header-ul trebuie scris o singură dată"

    def test_values_are_correct(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        m = make_epoch_metrics(epoch=3)
        logger.append_epoch_metrics(m)

        with open(tmp_path / "run01" / "metrics_by_epoch.csv") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert int(rows[0]["epoch"]) == 3
        assert float(rows[0]["val_auc"]) == pytest.approx(0.89, abs=1e-6)


class TestAppendRoundMetricsWithNone:
    """test_append_round_metrics_with_none_values"""

    def test_none_values_written_as_empty_string(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        m = RoundMetrics(
            round=1,
            num_clients=5,
            aggregation_method="fedavg",
            time_round_sec=10.0,
            update_norm=0.01,
            test_loss=None,
            test_auc=None,
            test_f1=None,
            test_f2=None,
            test_sensitivity=None,
            test_specificity=None,
            test_pr_auc=None,
        )
        logger.append_round_metrics(m)

        csv_path = tmp_path / "run01" / "central" / "metrics_by_round.csv"
        assert csv_path.exists()

        with open(csv_path) as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["test_auc"] == ""
        assert rows[0]["test_f1"] == ""
        assert rows[0]["test_f2"] == ""
        assert rows[0]["test_loss"] == ""

    def test_valid_values_written_correctly(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.append_round_metrics(make_round_metrics(round_num=2, test_auc=0.92))

        with open(tmp_path / "run01" / "central" / "metrics_by_round.csv") as f:
            rows = list(csv.DictReader(f))

        assert float(rows[0]["test_auc"]) == pytest.approx(0.92, abs=1e-6)
        assert int(rows[0]["round"]) == 2


class TestGetBestRound:
    """test_get_best_round_returns_max_auc"""

    def test_returns_round_with_max_auc(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        f2s = [0.80, 0.85, 0.92, 0.88, 0.91]
        for i, f2 in enumerate(f2s, 1):
            logger.append_round_metrics(make_round_metrics(round_num=i, test_f2=f2))

        best = logger.get_best_round()
        assert best == 3, f"Runda cu F2 maxim (0.92) este 3, nu {best}"

    def test_returns_first_on_tie(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        for i in range(1, 4):
            logger.append_round_metrics(make_round_metrics(round_num=i, test_f2=0.90))

        best = logger.get_best_round()
        assert best == 1, "La egalitate trebuie returnată prima rundă"

    def test_returns_none_if_file_missing(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        assert logger.get_best_round() is None

    def test_returns_none_if_all_auc_empty(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        m = RoundMetrics(
            round=1, num_clients=5, aggregation_method="fedavg",
            time_round_sec=10.0, update_norm=0.01,
            test_loss=None, test_auc=None, test_f1=None, test_f2=None,
            test_sensitivity=None, test_specificity=None, test_pr_auc=None,
        )
        logger.append_round_metrics(m)
        assert logger.get_best_round() is None


class TestSaveConfusionMatrix:
    """test_save_confusion_matrix_fields"""

    def test_all_required_fields_present(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        y_true = [0, 0, 1, 1, 1, 0, 1, 0]
        y_score = [0.1, 0.2, 0.8, 0.9, 0.7, 0.6, 0.85, 0.3]
        logger.save_confusion_matrix(y_true, y_score, threshold=0.5)

        cm_path = tmp_path / "run01" / "artifacts" / "best_model" / "confusion_matrix.json"
        assert cm_path.exists()

        with open(cm_path) as f:
            cm = json.load(f)

        required = {"threshold", "TP", "FP", "TN", "FN", "accuracy", "sensitivity", "specificity"}
        assert required.issubset(cm.keys()), f"Câmpuri lipsă: {required - cm.keys()}"

    def test_tp_fp_tn_fn_sum_to_total(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        y_true = [0, 0, 1, 1, 1, 0, 1, 0]
        y_score = [0.1, 0.2, 0.8, 0.9, 0.7, 0.6, 0.85, 0.3]
        logger.save_confusion_matrix(y_true, y_score)

        with open(tmp_path / "run01" / "artifacts" / "best_model" / "confusion_matrix.json") as f:
            cm = json.load(f)

        total = cm["TP"] + cm["FP"] + cm["TN"] + cm["FN"]
        assert total == len(y_true), f"TP+FP+TN+FN={total} ≠ {len(y_true)}"

    def test_threshold_stored_correctly(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.save_confusion_matrix([0, 1], [0.3, 0.8], threshold=0.5)

        with open(tmp_path / "run01" / "artifacts" / "best_model" / "confusion_matrix.json") as f:
            cm = json.load(f)

        assert cm["threshold"] == 0.5


class TestSavePredictions:
    """Teste pentru save_predictions"""

    def test_creates_csv_with_correct_columns(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.save_predictions(
            filenames=["img1.jpg", "img2.jpg"],
            y_true=[0, 1],
            y_score=[0.2, 0.8],
        )

        pred_path = tmp_path / "run01" / "artifacts" / "best_model" / "predictions_test.csv"
        assert pred_path.exists()

        with open(pred_path) as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 2
        assert set(rows[0].keys()) == {"filename", "y_true", "y_score"}
        assert rows[0]["filename"] == "img1.jpg"
        assert int(rows[0]["y_true"]) == 0
        assert float(rows[0]["y_score"]) == pytest.approx(0.2, abs=1e-6)


class TestUpdateRunConfig:
    """Teste pentru update_run_config"""

    def test_updates_existing_field(self, tmp_path):
        logger = ExperimentLogger(str(tmp_path / "run01"))
        logger.write_run_config({"run_id": "x", "early_stopped_at_epoch": None})
        logger.update_run_config({"early_stopped_at_epoch": 7})

        with open(tmp_path / "run01" / "run_config.json") as f:
            saved = json.load(f)

        assert saved["early_stopped_at_epoch"] == 7
        assert saved["run_id"] == "x"  # câmpul existent nu e șters


# ============================================================================
# Task 1.2 — Property 4: Round-trip CSV pentru metrici
# Feature: experiment-logging-and-visualization, Property 4: Round-trip CSV
# ============================================================================

class TestProperty4RoundTripCSV:

    @given(
        epoch=st.integers(min_value=1, max_value=100),
        train_loss=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        val_loss=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        val_auc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        val_f1=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        val_sensitivity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        val_specificity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        val_pr_auc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        lr=st.floats(min_value=1e-6, max_value=1.0, allow_nan=False),
        time_sec=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_epoch_metrics_roundtrip(
        self, epoch, train_loss, val_loss, val_auc, val_f1,
        val_sensitivity, val_specificity, val_pr_auc, lr, time_sec
    ):
        """Property 4: EpochMetrics scrise și citite din CSV sunt identice."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_{epoch}"))
            m = EpochMetrics(
                epoch=epoch, train_loss=train_loss, val_loss=val_loss,
                val_auc=val_auc, val_f1=val_f1, val_sensitivity=val_sensitivity,
                val_specificity=val_specificity, val_pr_auc=val_pr_auc,
                lr=lr, time_epoch_sec=time_sec,
            )
            logger.append_epoch_metrics(m)

            with open(Path(tmp) / f"run_{epoch}" / "metrics_by_epoch.csv") as f:
                rows = list(csv.DictReader(f))

            assert len(rows) == 1
            assert int(rows[0]["epoch"]) == epoch
            assert float(rows[0]["train_loss"]) == pytest.approx(train_loss, rel=1e-5, abs=1e-10)
            assert float(rows[0]["val_auc"]) == pytest.approx(val_auc, rel=1e-5, abs=1e-10)

    @given(
        round_num=st.integers(min_value=1, max_value=100),
        test_auc=st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        ),
        update_norm=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_round_metrics_roundtrip(self, round_num, test_auc, update_norm):
        """Property 4: RoundMetrics scrise și citite din CSV sunt identice."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_{round_num}"))
            m = RoundMetrics(
                round=round_num, num_clients=5, aggregation_method="fedavg",
                time_round_sec=10.0, update_norm=update_norm,
                test_loss=None, test_auc=test_auc, test_f1=None, test_f2=None,
                test_sensitivity=None, test_specificity=None, test_pr_auc=None,
            )
            logger.append_round_metrics(m)

            with open(Path(tmp) / f"run_{round_num}" / "central" / "metrics_by_round.csv") as f:
                rows = list(csv.DictReader(f))

            assert len(rows) == 1
            assert int(rows[0]["round"]) == round_num

            if test_auc is None:
                assert rows[0]["test_auc"] == ""
            else:
                assert float(rows[0]["test_auc"]) == pytest.approx(test_auc, rel=1e-5, abs=1e-10)

    @given(
        round_num=st.integers(min_value=1, max_value=100),
        node_id=st.sampled_from(["node1", "node2", "node3", "node4", "node5"]),
        val_auc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        delta_norm=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_node_metrics_roundtrip(self, round_num, node_id, val_auc, delta_norm):
        """Property 4: NodeRoundMetrics scrise și citite din CSV sunt identice."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_{round_num}_{node_id}"))
            m = NodeRoundMetrics(
                round=round_num, node_id=node_id, n_train_samples_used=500,
                val_auc=val_auc, val_f1=0.8, val_f2=0.78, val_sensitivity=0.85,
                val_specificity=0.75, val_pr_auc=0.82,
                local_train_time_sec=30.0, delta_norm=delta_norm,
            )
            logger.append_node_metrics(m)

            csv_path = Path(tmp) / f"run_{round_num}_{node_id}" / "nodes" / f"{node_id}_metrics_by_round.csv"
            with open(csv_path) as f:
                rows = list(csv.DictReader(f))

            assert len(rows) == 1
            assert rows[0]["node_id"] == node_id
            assert float(rows[0]["val_auc"]) == pytest.approx(val_auc, rel=1e-5, abs=1e-10)
            assert float(rows[0]["delta_norm"]) == pytest.approx(delta_norm, rel=1e-5, abs=1e-10)


# ============================================================================
# Task 1.3 — Property 6: Structura completă a run_config.json
# Feature: experiment-logging-and-visualization, Property 6: run_config structure
# ============================================================================

class TestProperty6RunConfigStructure:

    REQUIRED_CENTRALIZED = {
        "run_id", "experiment_type", "model_arch",
        "thresholding_policy", "timestamp", "git_commit_hash",
    }
    REQUIRED_FL = {
        "run_id", "experiment_type", "aggregation_method",
        "model_arch", "num_rounds", "local_epochs",
        "thresholding_policy", "timestamp", "git_commit_hash",
    }

    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
        model_arch=st.sampled_from(["resnet18", "densenet121", "efficientnet_b0"]),
    )
    @settings(max_examples=50)
    def test_centralized_config_has_required_fields(self, run_id, model_arch):
        """Property 6: run_config.json centralizat conține toate câmpurile obligatorii."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / run_id))
            logger.write_run_config({
                "run_id": run_id,
                "experiment_type": "centralized",
                "model_arch": model_arch,
                "thresholding_policy": "fixed_0.5",
            })

            with open(Path(tmp) / run_id / "run_config.json") as f:
                saved = json.load(f)

            missing = self.REQUIRED_CENTRALIZED - set(saved.keys())
            assert not missing, f"Câmpuri lipsă în run_config.json: {missing}"

    @given(
        run_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
        aggregation_method=st.sampled_from(["fedavg", "fedavgm", "fedprox"]),
        num_rounds=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=50)
    def test_fl_config_has_required_fields(self, run_id, aggregation_method, num_rounds):
        """Property 6: run_config.json FL conține toate câmpurile obligatorii."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / run_id))
            logger.write_run_config({
                "run_id": run_id,
                "experiment_type": "federated",
                "aggregation_method": aggregation_method,
                "model_arch": "efficientnet_b0",
                "num_rounds": num_rounds,
                "local_epochs": 1,
                "thresholding_policy": "fixed_0.5",
            })

            with open(Path(tmp) / run_id / "run_config.json") as f:
                saved = json.load(f)

            missing = self.REQUIRED_FL - set(saved.keys())
            assert not missing, f"Câmpuri lipsă în run_config.json FL: {missing}"


# ============================================================================
# Task 1.4 — Property 7: Selecția corectă a best round
# Feature: experiment-logging-and-visualization, Property 7: best round selection
# ============================================================================

class TestProperty7BestRoundSelection:

    @given(
        auc_values=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_returns_index_of_max_auc(self, auc_values):
        """Property 7: get_best_round() returnează runda cu F2 maxim."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_prop7"))
            for i, f2 in enumerate(auc_values, 1):
                logger.append_round_metrics(make_round_metrics(round_num=i, test_f2=f2))

            best = logger.get_best_round()
            assert best is not None

            expected_round = auc_values.index(max(auc_values)) + 1
            assert best == expected_round, (
                f"Așteptat runda {expected_round} (F2={max(auc_values):.4f}), primit {best}"
            )

    @given(
        n_rounds=st.integers(min_value=2, max_value=30),
        max_f2=st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_first_round_wins_on_tie(self, n_rounds, max_f2):
        """Property 7: La egalitate, prima rundă cu F2 maxim este returnată."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_tie"))
            for i in range(1, n_rounds + 1):
                logger.append_round_metrics(make_round_metrics(round_num=i, test_f2=max_f2))

            best = logger.get_best_round()
            assert best == 1, f"La egalitate trebuie returnată runda 1, nu {best}"


# ============================================================================
# Task 1.5 — Property 8: Structura și intervalele predictions_test.csv
# Feature: experiment-logging-and-visualization, Property 8: predictions CSV structure
# ============================================================================

class TestProperty8PredictionsCSVStructure:

    @given(
        n_samples=st.integers(min_value=1, max_value=200),
        labels=st.lists(st.integers(0, 1), min_size=1, max_size=200),
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=100)
    def test_predictions_csv_structure(self, n_samples, labels, scores):
        """Property 8: predictions_test.csv are structura și intervalele corecte."""
        import tempfile
        n = min(n_samples, len(labels), len(scores))
        assume(n >= 1)
        filenames = [f"img_{i}.jpg" for i in range(n)]
        y_true = labels[:n]
        y_score = scores[:n]

        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_p8"))
            logger.save_predictions(filenames, y_true, y_score)

            pred_path = Path(tmp) / "run_p8" / "artifacts" / "best_model" / "predictions_test.csv"
            assert pred_path.exists()

            with open(pred_path) as f:
                rows = list(csv.DictReader(f))

            assert len(rows) == n
            assert set(rows[0].keys()) == {"filename", "y_true", "y_score"}
            for row in rows:
                assert int(row["y_true"]) in {0, 1}
                assert 0.0 <= float(row["y_score"]) <= 1.0


# ============================================================================
# Task 1.6 — Property 9: Corectitudinea matematică a confusion_matrix.json
# Feature: experiment-logging-and-visualization, Property 9: confusion matrix math
# ============================================================================

class TestProperty9ConfusionMatrixMath:

    @given(
        y_true=st.lists(st.integers(0, 1), min_size=2, max_size=500),
        y_score=st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=2, max_size=500),
    )
    @settings(max_examples=100)
    def test_tp_fp_tn_fn_sum_to_total(self, y_true, y_score):
        """Property 9: TP+FP+TN+FN = total."""
        import tempfile
        n = min(len(y_true), len(y_score))
        assume(n >= 2)
        y_true, y_score = y_true[:n], y_score[:n]
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_p9a"))
            logger.save_confusion_matrix(y_true, y_score, threshold=0.5)
            with open(Path(tmp) / "run_p9a" / "artifacts" / "best_model" / "confusion_matrix.json") as f:
                cm = json.load(f)
        assert cm["TP"] + cm["FP"] + cm["TN"] + cm["FN"] == n

    @given(
        y_true=st.lists(st.integers(0, 1), min_size=2, max_size=200),
        y_score=st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=2, max_size=200),
    )
    @settings(max_examples=100)
    def test_accuracy_formula_correct(self, y_true, y_score):
        """Property 9: accuracy = (TP+TN) / total."""
        import tempfile
        n = min(len(y_true), len(y_score))
        assume(n >= 2)
        y_true, y_score = y_true[:n], y_score[:n]
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_p9b"))
            logger.save_confusion_matrix(y_true, y_score, threshold=0.5)
            with open(Path(tmp) / "run_p9b" / "artifacts" / "best_model" / "confusion_matrix.json") as f:
                cm = json.load(f)
        total = cm["TP"] + cm["FP"] + cm["TN"] + cm["FN"]
        expected_acc = (cm["TP"] + cm["TN"]) / total if total > 0 else 0.0
        assert cm["accuracy"] == pytest.approx(expected_acc, abs=1e-5)

    @given(
        y_true=st.lists(st.integers(0, 1), min_size=4, max_size=200),
        y_score=st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=4, max_size=200),
    )
    @settings(max_examples=100)
    def test_sensitivity_specificity_formulas(self, y_true, y_score):
        """Property 9: sensitivity = TP/(TP+FN), specificity = TN/(TN+FP)."""
        import tempfile
        n = min(len(y_true), len(y_score))
        assume(n >= 4)
        y_true, y_score = y_true[:n], y_score[:n]
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / "run_p9c"))
            logger.save_confusion_matrix(y_true, y_score, threshold=0.5)
            with open(Path(tmp) / "run_p9c" / "artifacts" / "best_model" / "confusion_matrix.json") as f:
                cm = json.load(f)
        tp, fp, tn, fn = cm["TP"], cm["FP"], cm["TN"], cm["FN"]
        if tp + fn > 0:
            assert cm["sensitivity"] == pytest.approx(tp / (tp + fn), abs=1e-5)
        if tn + fp > 0:
            assert cm["specificity"] == pytest.approx(tn / (tn + fp), abs=1e-5)


# ============================================================================
# Task 1.8 — Property 11: Header CSV scris o singură dată
# Feature: experiment-logging-and-visualization, Property 11: CSV header once
# ============================================================================

class TestProperty11CSVHeaderOnce:

    @given(n_rows=st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_epoch_metrics_header_once(self, n_rows):
        """Property 11: N apeluri append_epoch_metrics → 1 header + N rânduri."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_h{n_rows}"))
            for i in range(1, n_rows + 1):
                logger.append_epoch_metrics(make_epoch_metrics(epoch=i))
            csv_path = Path(tmp) / f"run_h{n_rows}" / "metrics_by_epoch.csv"
            with open(csv_path) as f:
                lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == n_rows + 1
            assert sum(1 for l in lines if l.startswith("epoch")) == 1

    @given(n_rows=st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_round_metrics_header_once(self, n_rows):
        """Property 11: N apeluri append_round_metrics → 1 header + N rânduri."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_rh{n_rows}"))
            for i in range(1, n_rows + 1):
                logger.append_round_metrics(make_round_metrics(round_num=i))
            csv_path = Path(tmp) / f"run_rh{n_rows}" / "central" / "metrics_by_round.csv"
            with open(csv_path) as f:
                lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == n_rows + 1
            assert sum(1 for l in lines if l.startswith("round")) == 1

    @given(n_rows=st.integers(min_value=1, max_value=50))
    @settings(max_examples=100)
    def test_node_metrics_header_once(self, n_rows):
        """Property 11: N apeluri append_node_metrics → 1 header + N rânduri."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            logger = ExperimentLogger(str(Path(tmp) / f"run_nh{n_rows}"))
            for i in range(1, n_rows + 1):
                logger.append_node_metrics(make_node_metrics(round_num=i, node_id="node1"))
            csv_path = Path(tmp) / f"run_nh{n_rows}" / "nodes" / "node1_metrics_by_round.csv"
            with open(csv_path) as f:
                lines = [l for l in f.readlines() if l.strip()]
            assert len(lines) == n_rows + 1
            assert sum(1 for l in lines if l.startswith("round")) == 1
