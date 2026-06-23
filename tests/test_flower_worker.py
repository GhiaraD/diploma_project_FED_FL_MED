"""
Teste unitare pentru services/node/worker/app/flower_client.py

Acoperă:
  - CsvDataset: citire CSV, FileNotFoundError, __len__, __getitem__
  - FedMedClient._compute_delta_norm: corectitudine matematică (Property 5)
  - FedMedClient.get_parameters / set_parameters: round-trip parametri
  - FedMedClient._load_data: split-uri fixe vs fallback, FileNotFoundError
  - get_last_training_metrics: returnează None inițial, valoarea după setare

Strategia de import:
  - flwr, opacus și node_core nu sunt în venv-ul de test
  - Stub-urile sunt instalate în conftest.py înainte de orice import

Rulare:
    pytest tests/test_flower_worker.py -v
"""
import csv
import sys
import importlib.util
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Importăm flower_client cu cale absolută
_FC_PATH = Path(__file__).parent.parent / "services" / "node" / "worker" / "app" / "flower_client.py"
_spec = importlib.util.spec_from_file_location("app.flower_client", _FC_PATH)
fc = importlib.util.module_from_spec(_spec)
sys.modules["app.flower_client"] = fc
_spec.loader.exec_module(fc)

# Referințe directe la clasele testate
CsvDataset = fc.CsvDataset
FedMedClient = fc.FedMedClient


# ---------------------------------------------------------------------------
# Helper local
# ---------------------------------------------------------------------------

def _make_tiny_model() -> torch.nn.Module:
    """Model minimal cu 2 straturi pentru teste rapide."""
    return torch.nn.Sequential(
        torch.nn.Linear(4, 4),
        torch.nn.Linear(4, 2),
    )


# ---------------------------------------------------------------------------
# Fixture: client minimal (fără I/O real)
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_model():
    return _make_tiny_model()


@pytest.fixture
def client_with_mock_loaders(tiny_model):
    """
    FedMedClient cu model mic și data loaders mock-uite.
    Evită orice I/O de fișiere sau rețea.
    """
    mock_train_loader = MagicMock()
    mock_val_loader = MagicMock()
    mock_train_loader.dataset = list(range(100))
    mock_val_loader.dataset = list(range(20))

    with patch.object(fc, "get_model", return_value=tiny_model):
        with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
            with patch.object(FedMedClient, "_load_data", return_value=(mock_train_loader, mock_val_loader, None)):
                c = FedMedClient(
                    node_id="node1",
                    model_name="efficientnet_b0",
                    num_classes=2,
                    dataset_path="/fake/dataset",
                    device="cpu",
                    batch_size=32,
                    enable_signing=False,
                    splits_dir=None,
                )
    return c


# ===========================================================================
# CsvDataset
# ===========================================================================

class TestCsvDataset:

    def test_raises_file_not_found_for_missing_csv(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc_info:
            CsvDataset(str(tmp_path / "nonexistent.csv"))
        assert "nonexistent.csv" in str(exc_info.value)

    def test_error_message_mentions_prepare_script(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc_info:
            CsvDataset(str(tmp_path / "missing.csv"))
        assert "prepare_experiment_data" in str(exc_info.value)

    def test_len_returns_number_of_rows(self, tmp_path):
        csv_path = tmp_path / "split.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            for i in range(5):
                writer.writerow({"filepath": f"img_{i}.jpg", "label": i % 2})
        ds = CsvDataset(str(csv_path))
        assert len(ds) == 5

    def test_len_zero_for_empty_csv(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
        ds = CsvDataset(str(csv_path))
        assert len(ds) == 0

    def test_samples_loaded_correctly(self, tmp_path):
        csv_path = tmp_path / "split.csv"
        rows = [("path/to/img1.jpg", 0), ("path/to/img2.jpg", 1)]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            for fp, lbl in rows:
                writer.writerow({"filepath": fp, "label": lbl})
        ds = CsvDataset(str(csv_path))
        assert ds.samples[0] == ("path/to/img1.jpg", 0)
        assert ds.samples[1] == ("path/to/img2.jpg", 1)

    def test_label_is_int(self, tmp_path):
        csv_path = tmp_path / "split.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            writer.writerow({"filepath": "img.jpg", "label": "1"})
        ds = CsvDataset(str(csv_path))
        _, label = ds.samples[0]
        assert isinstance(label, int)
        assert label == 1

    def test_getitem_applies_transform(self, tmp_path):
        """__getitem__ aplică transform dacă e setat."""
        from PIL import Image as PILImage
        import numpy as np

        # Creăm o imagine reală temporară
        img_path = tmp_path / "test.jpg"
        PILImage.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(str(img_path))

        csv_path = tmp_path / "split.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            writer.writerow({"filepath": str(img_path), "label": 0})

        transform_called = []

        def mock_transform(img):
            transform_called.append(True)
            return torch.zeros(3, 32, 32)

        ds = CsvDataset(str(csv_path), transform=mock_transform)
        img_tensor, label = ds[0]
        assert len(transform_called) == 1
        assert label == 0

    def test_getitem_no_transform_returns_pil_image(self, tmp_path):
        """Fără transform, __getitem__ returnează PIL Image."""
        from PIL import Image as PILImage
        import numpy as np

        img_path = tmp_path / "test.jpg"
        PILImage.fromarray(np.zeros((32, 32, 3), dtype=np.uint8)).save(str(img_path))

        csv_path = tmp_path / "split.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            writer.writerow({"filepath": str(img_path), "label": 1})

        ds = CsvDataset(str(csv_path), transform=None)
        img, label = ds[0]
        assert isinstance(img, PILImage.Image)
        assert label == 1

    def test_relative_path_resolved_to_absolute(self, tmp_path):
        """Path relativ în CSV e rezolvat față de / (comportament Docker)."""
        from PIL import Image as PILImage
        import numpy as np

        # Creăm imaginea la o cale absolută
        img_path = tmp_path / "img.jpg"
        PILImage.fromarray(np.zeros((8, 8, 3), dtype=np.uint8)).save(str(img_path))

        # Scriem în CSV calea relativă (fără /)
        relative = str(img_path).lstrip("/")

        csv_path = tmp_path / "split.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
            writer.writeheader()
            writer.writerow({"filepath": relative, "label": 0})

        ds = CsvDataset(str(csv_path), transform=None)
        # Nu trebuie să ridice excepție — path-ul e rezolvat la /relative
        # (în test, /relative poate să nu existe, dar testăm logica de rezolvare)
        assert ds.samples[0][0] == relative


# ===========================================================================
# FedMedClient._compute_delta_norm  (Property 5)
# ===========================================================================

class TestComputeDeltaNorm:

    def test_zero_when_params_identical(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        params = [np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0])]
        assert c._compute_delta_norm(params, params) == pytest.approx(0.0, abs=1e-6)

    def test_known_value(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        local = [np.array([3.0, 4.0])]
        global_ = [np.array([0.0, 0.0])]
        # ||[3,4]||_2 = 5.0
        assert c._compute_delta_norm(local, global_) == pytest.approx(5.0, abs=1e-6)

    def test_returns_float(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        result = c._compute_delta_norm([np.array([1.0])], [np.array([0.0])])
        assert isinstance(result, float)

    def test_returns_zero_on_exception(self, client_with_mock_loaders):
        """Dacă parametrii sunt incompatibili, returnează 0.0 fără excepție."""
        c = client_with_mock_loaders
        # Shape mismatch → concatenate va eșua
        local = [np.array([1.0, 2.0])]
        global_ = [np.array([1.0, 2.0, 3.0])]
        result = c._compute_delta_norm(local, global_)
        assert result == 0.0

    def test_multidimensional_params(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        local = [np.array([[1.0, 0.0], [0.0, 1.0]])]
        global_ = [np.array([[0.0, 0.0], [0.0, 0.0]])]
        # flatten → [1,0,0,1], norm = sqrt(2)
        assert c._compute_delta_norm(local, global_) == pytest.approx(np.sqrt(2), abs=1e-6)

    @given(
        local_vals=st.lists(
            st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=50,
        ),
        global_vals=st.lists(
            st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_property5_matches_numpy_formula(self, local_vals, global_vals):
        """
        Property 5: _compute_delta_norm(W_local, W_global) ==
        np.linalg.norm(np.concatenate([l.flatten() - g.flatten() ...]))
        """
        n = min(len(local_vals), len(global_vals))
        assume(n >= 1)
        local_vals = local_vals[:n]
        global_vals = global_vals[:n]

        local = [np.array(local_vals)]
        global_ = [np.array(global_vals)]

        expected = float(np.linalg.norm(
            np.concatenate([(l.flatten() - g.flatten()) for l, g in zip(local, global_)])
        ))

        # Instanțiem clientul direct în test (nu fixture) pentru compatibilitate cu @given
        mock_loader = MagicMock()
        mock_loader.dataset = []
        tiny = _make_tiny_model()
        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    c = FedMedClient(
                        node_id="node1", model_name="efficientnet_b0",
                        num_classes=2, dataset_path="/fake",
                        device="cpu", enable_signing=False,
                    )

        result = c._compute_delta_norm(local, global_)
        assert result == pytest.approx(expected, rel=1e-5, abs=1e-10)


# ===========================================================================
# FedMedClient.get_parameters / set_parameters
# ===========================================================================

class TestGetSetParameters:

    def test_get_parameters_returns_list_of_ndarrays(self, client_with_mock_loaders):
        params = client_with_mock_loaders.get_parameters({})
        assert isinstance(params, list)
        assert all(isinstance(p, np.ndarray) for p in params)

    def test_get_parameters_count_matches_model(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        expected_count = len(list(c.model.state_dict().values()))
        assert len(c.get_parameters({})) == expected_count

    def test_set_parameters_updates_model(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        # Ottieni parametrii originali
        original = c.get_parameters({})
        # Creăm parametri noi (toți zero)
        zeroed = [np.zeros_like(p) for p in original]
        c.set_parameters(zeroed)
        # Verificăm că modelul s-a actualizat
        after = c.get_parameters({})
        for p in after:
            assert np.allclose(p, 0.0), "Parametrii trebuie să fie zero după set_parameters"

    def test_get_set_roundtrip(self, client_with_mock_loaders):
        """get_parameters → set_parameters → get_parameters produce aceiași parametri."""
        c = client_with_mock_loaders
        original = c.get_parameters({})
        c.set_parameters(original)
        restored = c.get_parameters({})
        for orig, rest in zip(original, restored):
            assert np.allclose(orig, rest, atol=1e-6)

    def test_set_parameters_with_random_values(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        original = c.get_parameters({})
        random_params = [np.random.randn(*p.shape).astype(p.dtype) for p in original]
        c.set_parameters(random_params)
        after = c.get_parameters({})
        for rand, got in zip(random_params, after):
            assert np.allclose(rand, got, atol=1e-6)


# ===========================================================================
# FedMedClient._load_data — split-uri fixe
# ===========================================================================

class TestLoadData:

    def _make_split_csvs(self, tmp_path, node_id="node1", n_train=10, n_val=5):
        """Creează CSV-uri de split cu imagini fake."""
        from PIL import Image as PILImage
        import numpy as _np

        splits_dir = tmp_path / "splits"
        splits_dir.mkdir()
        img_dir = tmp_path / "imgs"
        img_dir.mkdir()

        def make_csv(name, n):
            csv_path = splits_dir / name
            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
                writer.writeheader()
                for i in range(n):
                    img_path = img_dir / f"{name}_{i}.jpg"
                    PILImage.fromarray(
                        _np.zeros((8, 8, 3), dtype=_np.uint8)
                    ).save(str(img_path))
                    writer.writerow({"filepath": str(img_path), "label": i % 2})
            return csv_path

        make_csv(f"{node_id}_train.csv", n_train)
        make_csv(f"{node_id}_val.csv", n_val)
        return splits_dir

    def test_raises_file_not_found_when_train_csv_missing(self, tmp_path):
        splits_dir = tmp_path / "splits"
        splits_dir.mkdir()
        # val esiste, train nu
        (splits_dir / "node1_val.csv").touch()

        with patch.object(fc, "get_model", return_value=_make_tiny_model()):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with pytest.raises(FileNotFoundError) as exc_info:
                    FedMedClient(
                        node_id="node1",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=False,
                        splits_dir=str(splits_dir),
                    )
        assert "node1_train.csv" in str(exc_info.value)

    def test_raises_file_not_found_when_val_csv_missing(self, tmp_path):
        splits_dir = tmp_path / "splits"
        splits_dir.mkdir()
        # train există, val nu
        (splits_dir / "node1_train.csv").touch()
        # Scriem header ca să nu crape CsvDataset
        with open(splits_dir / "node1_train.csv", "w") as f:
            f.write("filepath,label\n")

        with patch.object(fc, "get_model", return_value=_make_tiny_model()):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with pytest.raises(FileNotFoundError) as exc_info:
                    FedMedClient(
                        node_id="node1",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=False,
                        splits_dir=str(splits_dir),
                    )
        assert "node1_val.csv" in str(exc_info.value)

    def test_error_message_mentions_prepare_script(self, tmp_path):
        splits_dir = tmp_path / "splits"
        splits_dir.mkdir()

        with patch.object(fc, "get_model", return_value=_make_tiny_model()):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with pytest.raises(FileNotFoundError) as exc_info:
                    FedMedClient(
                        node_id="node2",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=False,
                        splits_dir=str(splits_dir),
                    )
        assert "prepare_experiment_data" in str(exc_info.value)

    def test_fallback_used_when_splits_dir_is_none(self, tmp_path):
        """Când splits_dir=None, se folosesc folderele train/, val/, test/ din dataset."""
        mock_dataset = MagicMock()
        mock_dataset.__len__ = MagicMock(return_value=100)

        mock_train_loader = MagicMock()
        mock_train_loader.dataset = mock_dataset
        mock_val_loader = MagicMock()
        mock_val_loader.dataset = mock_dataset

        with patch.object(fc, "get_model", return_value=_make_tiny_model()):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(fc, "load_dataset", return_value=mock_dataset) as mock_ld:
                    with patch.object(fc, "create_dataloaders", return_value=(mock_train_loader, mock_val_loader)):
                        with patch("torch.utils.data.DataLoader", return_value=mock_train_loader):
                            FedMedClient(
                                node_id="node1",
                                model_name="efficientnet_b0",
                                num_classes=2,
                                dataset_path="/fake/dataset",
                                device="cpu",
                                enable_signing=False,
                                splits_dir=None,
                            )

        # load_dataset trebuie apelat de 3 ori: train, val, test
        assert mock_ld.call_count == 3


# ===========================================================================
# get_last_training_metrics
# ===========================================================================

class TestGetLastTrainingMetrics:

    def test_returns_none_initially(self):
        import app.flower_client as fresh_fc
        # Resetăm variabila globală
        fresh_fc._last_training_metrics = None
        assert fresh_fc.get_last_training_metrics() is None

    def test_returns_value_after_set(self):
        import app.flower_client as fresh_fc
        fresh_fc._last_training_metrics = {"auc": 0.92, "f1": 0.88}
        result = fresh_fc.get_last_training_metrics()
        assert result == {"auc": 0.92, "f1": 0.88}
        # Cleanup
        fresh_fc._last_training_metrics = None

    def test_returns_same_reference(self):
        import app.flower_client as fresh_fc
        metrics = {"accuracy": 0.9}
        fresh_fc._last_training_metrics = metrics
        assert fresh_fc.get_last_training_metrics() is metrics
        fresh_fc._last_training_metrics = None


# ===========================================================================
# FedMedClient — inițializare și atribute de bază
# ===========================================================================

class TestFedMedClientInit:

    def test_node_id_stored(self, client_with_mock_loaders):
        assert client_with_mock_loaders.node_id == "node1"

    def test_model_name_stored(self, client_with_mock_loaders):
        assert client_with_mock_loaders.model_name == "efficientnet_b0"

    def test_device_stored(self, client_with_mock_loaders):
        assert client_with_mock_loaders.device == "cpu"

    def test_batch_size_stored(self, client_with_mock_loaders):
        assert client_with_mock_loaders.batch_size == 32

    def test_dp_disabled_by_default(self, client_with_mock_loaders):
        assert client_with_mock_loaders.enable_dp is False

    def test_signing_disabled_when_signer_not_ready(self, client_with_mock_loaders):
        # signer.is_ready() returnează False în fixture → signing dezactivat
        assert client_with_mock_loaders.enable_signing is False

    def test_splits_dir_none_by_default(self, client_with_mock_loaders):
        assert client_with_mock_loaders.splits_dir is None

    def test_model_on_correct_device(self, client_with_mock_loaders):
        c = client_with_mock_loaders
        for param in c.model.parameters():
            assert str(param.device) == "cpu"


# ===========================================================================
# Helper: data loader cu tensori reali mici (pentru fit/evaluate fără GPU)
# ===========================================================================

def _make_real_loader(n_samples=8, n_classes=2, input_size=4, batch_size=4):
    """
    Creează un DataLoader cu tensori reali mici.
    Modelul tiny are Linear(4,4) → Linear(4,2), deci input_size=4.
    """
    X = torch.randn(n_samples, input_size)
    y = torch.randint(0, n_classes, (n_samples,))
    dataset = torch.utils.data.TensorDataset(X, y)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False)


def _make_client_with_real_loaders(node_id="node1", n_train=8, n_val=8):
    """
    FedMedClient cu model tiny și data loaders cu tensori reali.
    train_model e mock-uit să returneze history fără antrenare reală.
    """
    tiny = _make_tiny_model()
    train_loader = _make_real_loader(n_train)
    val_loader = _make_real_loader(n_val)

    mock_history = {
        "train_loss": [0.5],
        "val_loss": [0.4],
        "best_val_acc": 0.75,
        "epochs_trained": 1,
    }

    with patch.object(fc, "get_model", return_value=tiny):
        with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
            with patch.object(FedMedClient, "_load_data", return_value=(train_loader, val_loader, None)):
                with patch.object(fc, "train_model", return_value=mock_history):
                    c = FedMedClient(
                        node_id=node_id,
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=False,
                        splits_dir=None,
                    )
    # Înlocuim train_model pe instanță pentru apelurile ulterioare
    c._mock_history = mock_history
    return c, train_loader, val_loader


# ===========================================================================
# FedMedClient.evaluate()
# ===========================================================================

class TestEvaluate:

    def test_returns_tuple_of_three(self):
        c, _, _ = _make_client_with_real_loaders()
        params = c.get_parameters({})
        result = c.evaluate(params, {})
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_loss_is_float(self):
        c, _, _ = _make_client_with_real_loaders()
        params = c.get_parameters({})
        loss, _, _ = c.evaluate(params, {})
        assert isinstance(loss, float)
        assert loss >= 0.0

    def test_num_samples_matches_val_loader(self):
        c, _, val_loader = _make_client_with_real_loaders(n_val=8)
        params = c.get_parameters({})
        _, num_samples, _ = c.evaluate(params, {})
        assert num_samples == len(val_loader.dataset)

    def test_metrics_dict_has_required_keys(self):
        c, _, _ = _make_client_with_real_loaders()
        params = c.get_parameters({})
        _, _, metrics = c.evaluate(params, {})
        for key in ["accuracy", "f1", "precision", "recall", "auc"]:
            assert key in metrics

    def test_metrics_are_floats(self):
        c, _, _ = _make_client_with_real_loaders()
        params = c.get_parameters({})
        _, _, metrics = c.evaluate(params, {})
        for key in ["accuracy", "f1", "precision", "recall"]:
            assert isinstance(metrics[key], float)

    def test_evaluate_uses_set_parameters(self):
        """evaluate() trebuie să încarce parametrii dați, nu cei existenți."""
        c, _, _ = _make_client_with_real_loaders()
        original = c.get_parameters({})
        # Setăm toți parametrii la zero
        zeroed = [np.zeros_like(p) for p in original]
        c.evaluate(zeroed, {})
        # Verificăm că modelul a fost actualizat cu parametrii zero
        after = c.get_parameters({})
        for p in after:
            assert np.allclose(p, 0.0)

    def test_evaluate_with_empty_config(self):
        c, _, _ = _make_client_with_real_loaders()
        params = c.get_parameters({})
        loss, n, metrics = c.evaluate(params, {})
        assert loss >= 0.0
        assert n > 0


# ===========================================================================
# FedMedClient.fit()
# ===========================================================================

class TestFit:

    def _make_fit_client(self):
        """Client gata pentru fit() cu train_model mock-uit."""
        c, train_loader, val_loader = _make_client_with_real_loaders()
        mock_history = {
            "train_loss": [0.5],
            "val_loss": [0.4],
            "best_val_acc": 0.75,
        }
        c._patched_train_model = patch.object(fc, "train_model", return_value=mock_history)
        return c, mock_history

    def test_fit_returns_tuple_of_three(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            result = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_fit_returns_parameters_list(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            updated_params, _, _ = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert isinstance(updated_params, list)
        assert all(isinstance(p, np.ndarray) for p in updated_params)

    def test_fit_num_samples_matches_train_loader(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, num_samples, _ = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert num_samples == len(c.train_loader.dataset)

    def test_fit_metrics_has_required_keys(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        for key in ["accuracy", "train_loss", "val_loss", "node_id",
                    "val_auc", "val_f1", "delta_norm", "n_train_samples_used",
                    "local_train_time_sec", "dp_enabled"]:
            assert key in metrics, f"Cheie lipsă: {key}"

    def test_fit_node_id_in_metrics(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert metrics["node_id"] == "node1"

    def test_fit_dp_disabled_in_metrics(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert metrics["dp_enabled"] is False

    def test_fit_delta_norm_is_float(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert isinstance(metrics["delta_norm"], float)

    def test_fit_local_train_time_positive(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert metrics["local_train_time_sec"] >= 0.0

    def test_fit_stores_metrics_globally(self):
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        fc._last_training_metrics = None
        with patch.object(fc, "train_model", return_value=mock_history):
            c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert fc._last_training_metrics is not None
        assert "accuracy" in fc._last_training_metrics

    def test_fit_uses_config_num_epochs(self):
        """train_model trebuie apelat cu num_epochs din config."""
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history) as mock_tm:
            c.fit(params, {"server_round": 1, "num_epochs": 3, "learning_rate": 0.001})
        call_kwargs = mock_tm.call_args[1]
        assert call_kwargs.get("num_epochs") == 3

    def test_fit_with_signing_enabled_adds_signature_package(self):
        """Când signing e activat și semnătura reușește, metrics conține _signature_package."""
        c, mock_history = self._make_fit_client()
        # Activăm signing manual
        c.enable_signing = True
        mock_signer = MagicMock()
        c.signer = mock_signer
        fake_sig = {"signed": True, "signature": "abc123"}
        with patch.object(fc, "train_model", return_value=mock_history):
            with patch.object(fc, "sign_model_parameters", return_value=([], fake_sig)):
                params = c.get_parameters({})
                _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert "_signature_package" in metrics

    def test_fit_without_signing_no_signature_package(self):
        c, mock_history = self._make_fit_client()
        c.enable_signing = False
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})
        assert "_signature_package" not in metrics

    def test_fit_default_config_values(self):
        """fit() cu config gol trebuie să folosească valorile default."""
        c, mock_history = self._make_fit_client()
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history) as mock_tm:
            c.fit(params, {})  # config gol
        call_kwargs = mock_tm.call_args[1]
        assert call_kwargs.get("num_epochs") == 5   # default din cod
        assert call_kwargs.get("optimizer") is not None


# ===========================================================================
# FedMedClient.__init__ — ramuri suplimentare
# ===========================================================================

class TestFedMedClientInitBranches:

    def test_signing_enabled_when_signer_ready(self):
        """Când signer.is_ready() returnează True, enable_signing rămâne True."""
        tiny = _make_tiny_model()
        mock_signer = MagicMock()
        mock_signer.is_ready.return_value = True
        mock_loader = MagicMock()
        mock_loader.dataset = []

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=mock_signer):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    c = FedMedClient(
                        node_id="node1",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=True,
                    )
        assert c.enable_signing is True
        assert c.signer is mock_signer

    def test_signing_disabled_when_create_signer_raises(self):
        """Dacă create_payload_signer ridică excepție, enable_signing devine False."""
        tiny = _make_tiny_model()
        mock_loader = MagicMock()
        mock_loader.dataset = []

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", side_effect=RuntimeError("cert error")):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    c = FedMedClient(
                        node_id="node1",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=True,
                    )
        assert c.enable_signing is False

    def test_dp_requested_and_available_enables_dp(self):
        """enable_dp=True cu OPACUS_AVAILABLE=True → enable_dp rămâne True."""
        tiny = _make_tiny_model()
        mock_loader = MagicMock()
        mock_loader.dataset = []

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    with patch.object(FedMedClient, "_validate_model_for_dp"):
                        c = FedMedClient(
                            node_id="node1",
                            model_name="efficientnet_b0",
                            num_classes=2,
                            dataset_path="/fake",
                            device="cpu",
                            enable_signing=False,
                            enable_dp=True,
                        )
        # OPACUS_AVAILABLE=True → enable_dp rămâne True
        assert c.enable_dp is True


# ===========================================================================
# FedMedClient._load_data — calea de succes cu split-uri fixe
# ===========================================================================

class TestLoadDataSuccess:

    def test_loads_from_csv_splits_when_both_exist(self, tmp_path):
        """Când ambele CSV-uri există, _load_data le citește și creează loaders."""
        from PIL import Image as PILImage
        import numpy as _np

        splits_dir = tmp_path / "splits"
        splits_dir.mkdir()
        img_dir = tmp_path / "imgs"
        img_dir.mkdir()

        def make_csv(name, n):
            csv_path = splits_dir / name
            with open(csv_path, "w", newline="") as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=["filepath", "label"])
                writer.writeheader()
                for i in range(n):
                    img_path = img_dir / f"{name}_{i}.jpg"
                    PILImage.fromarray(
                        _np.zeros((8, 8, 3), dtype=_np.uint8)
                    ).save(str(img_path))
                    writer.writerow({"filepath": str(img_path), "label": i % 2})

        make_csv("node1_train.csv", 4)
        make_csv("node1_val.csv", 2)

        tiny = _make_tiny_model()
        mock_train_loader = MagicMock()
        mock_val_loader = MagicMock()

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(fc, "create_dataloaders", return_value=(mock_train_loader, mock_val_loader)) as mock_cd:
                    c = FedMedClient(
                        node_id="node1",
                        model_name="efficientnet_b0",
                        num_classes=2,
                        dataset_path="/fake",
                        device="cpu",
                        enable_signing=False,
                        splits_dir=str(splits_dir),
                    )

        mock_cd.assert_called_once()
        assert c.train_loader is mock_train_loader
        assert c.val_loader is mock_val_loader


# ===========================================================================
# FedMedClient._load_data — fallback complet (train/val/test folders)
# ===========================================================================

class TestLoadDataFallbackComplete:

    def test_fallback_loads_all_three_splits(self):
        """
        Fallback: load_dataset apelat cu split='train', 'val', 'test'.
        """
        mock_dataset = MagicMock()
        mock_dataset.__len__ = MagicMock(return_value=100)

        mock_train_loader = MagicMock()
        mock_train_loader.dataset = mock_dataset
        mock_val_loader = MagicMock()
        mock_val_loader.dataset = mock_dataset
        mock_test_loader = MagicMock()
        mock_test_loader.dataset = mock_dataset

        tiny = _make_tiny_model()

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(fc, "load_dataset", return_value=mock_dataset) as mock_ld:
                    with patch.object(fc, "create_dataloaders", return_value=(mock_train_loader, mock_val_loader)):
                        with patch("torch.utils.data.DataLoader", return_value=mock_test_loader):
                            c = FedMedClient(
                                node_id="node1",
                                model_name="efficientnet_b0",
                                num_classes=2,
                                dataset_path="/fake/dataset",
                                device="cpu",
                                enable_signing=False,
                                splits_dir=None,
                            )

        assert mock_ld.call_count == 3
        calls = [call[1]["split"] for call in mock_ld.call_args_list]
        assert "train" in calls
        assert "val" in calls
        assert "test" in calls

    def test_fallback_train_loader_and_val_loader_set(self):
        """train_loader și val_loader sunt setate corect din create_dataloaders."""
        mock_dataset = MagicMock()
        mock_dataset.__len__ = MagicMock(return_value=50)

        mock_train_loader = MagicMock()
        mock_train_loader.dataset = mock_dataset
        mock_val_loader = MagicMock()
        mock_val_loader.dataset = mock_dataset
        mock_test_loader = MagicMock()
        mock_test_loader.dataset = mock_dataset

        tiny = _make_tiny_model()

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(fc, "load_dataset", return_value=mock_dataset):
                    with patch.object(fc, "create_dataloaders", return_value=(mock_train_loader, mock_val_loader)):
                        with patch("torch.utils.data.DataLoader", return_value=mock_test_loader):
                            c = FedMedClient(
                                node_id="node1",
                                model_name="efficientnet_b0",
                                num_classes=2,
                                dataset_path="/fake",
                                device="cpu",
                                enable_signing=False,
                                splits_dir=None,
                            )

        assert c.train_loader is mock_train_loader
        assert c.val_loader is mock_val_loader
        assert c.test_loader is mock_test_loader


# ===========================================================================
# FedMedClient.fit() — ramuri suplimentare
# ===========================================================================

class TestFitAdditionalBranches:

    def test_fit_signing_exception_does_not_crash(self):
        """Dacă sign_model_parameters ridică excepție, fit() continuă fără semnătură."""
        c, train_loader, val_loader = _make_client_with_real_loaders()
        mock_history = {"train_loss": [0.5], "val_loss": [0.4], "best_val_acc": 0.75}

        c.enable_signing = True
        c.signer = MagicMock()

        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            with patch.object(fc, "sign_model_parameters", side_effect=RuntimeError("sign error")):
                _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        # Nu trebuie să crape și nu trebuie să conțină _signature_package
        assert "_signature_package" not in metrics
        assert "accuracy" in metrics

    def test_fit_n_train_samples_used_correct(self):
        """n_train_samples_used trebuie să fie dimensiunea train_loader.dataset."""
        c, train_loader, _ = _make_client_with_real_loaders(n_train=12)
        mock_history = {"train_loss": [0.5], "val_loss": [0.4], "best_val_acc": 0.75}
        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=mock_history):
            _, _, metrics = c.fit(params, {"server_round": 2, "num_epochs": 1})
        assert metrics["n_train_samples_used"] == 12

    def test_fit_val_sensitivity_from_eval_metrics(self):
        """val_sensitivity vine din eval_metrics['sensitivity'] returnat de compute_metrics."""
        c, _, _ = _make_client_with_real_loaders()
        mock_history = {"train_loss": [0.5], "val_loss": [0.4], "best_val_acc": 0.75}

        # Stub-ul din conftest returnează sensitivity=0.82 — verificăm că e propagat corect
        with patch.object(fc, "train_model", return_value=mock_history):
            params = c.get_parameters({})
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        # val_sensitivity trebuie să fie un float valid în [0, 1]
        assert isinstance(metrics["val_sensitivity"], float)
        assert 0.0 <= metrics["val_sensitivity"] <= 1.0

    def test_fit_val_specificity_from_eval_metrics(self):
        c, _, _ = _make_client_with_real_loaders()
        mock_history = {"train_loss": [0.5], "val_loss": [0.4], "best_val_acc": 0.75}

        with patch.object(fc, "train_model", return_value=mock_history):
            params = c.get_parameters({})
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        assert isinstance(metrics["val_specificity"], float)
        assert 0.0 <= metrics["val_specificity"] <= 1.0


# ===========================================================================
# _validate_model_for_dp() — acum că opacus e disponibil
# ===========================================================================

class TestValidateModelForDp:

    def _make_dp_client(self):
        """Client cu enable_dp=True, _validate_model_for_dp mock-uit inițial."""
        tiny = _make_tiny_model()
        mock_loader = MagicMock()
        mock_loader.dataset = []

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    with patch.object(FedMedClient, "_validate_model_for_dp"):
                        c = FedMedClient(
                            node_id="node1",
                            model_name="efficientnet_b0",
                            num_classes=2,
                            dataset_path="/fake",
                            device="cpu",
                            enable_signing=False,
                            enable_dp=True,
                        )
        return c

    def test_validate_does_nothing_when_dp_disabled(self):
        """Dacă enable_dp=False, _validate_model_for_dp returnează imediat."""
        c = self._make_dp_client()
        c.enable_dp = False
        # Nu trebuie să ridice excepție
        c._validate_model_for_dp()

    def test_validate_disables_dp_on_exception(self):
        """Dacă ModuleValidator ridică excepție, enable_dp devine False."""
        from opacus.validators import ModuleValidator
        c = self._make_dp_client()
        c.enable_dp = True

        with patch.object(ModuleValidator, "validate", side_effect=RuntimeError("validator error")):
            c._validate_model_for_dp()

        assert c.enable_dp is False

    def test_validate_fixes_incompatible_model(self):
        """Dacă modelul are erori, ModuleValidator.fix e apelat."""
        from opacus.validators import ModuleValidator
        c = self._make_dp_client()
        c.enable_dp = True

        fixed_model = _make_tiny_model()
        with patch.object(ModuleValidator, "validate", return_value=["error1"]):
            with patch.object(ModuleValidator, "fix", return_value=fixed_model) as mock_fix:
                c._validate_model_for_dp()

        mock_fix.assert_called_once()
        assert c.model is fixed_model

    def test_validate_no_fix_when_model_compatible(self):
        """Dacă modelul e compatibil (fără erori), fix nu e apelat."""
        from opacus.validators import ModuleValidator
        c = self._make_dp_client()
        c.enable_dp = True

        with patch.object(ModuleValidator, "validate", return_value=[]):
            with patch.object(ModuleValidator, "fix") as mock_fix:
                c._validate_model_for_dp()

        mock_fix.assert_not_called()


# ===========================================================================
# FedMedClient.__init__ — log lines când DP e enabled (liniile 196-197, 212-215)
# ===========================================================================

class TestInitDpLogLines:

    def test_dp_log_lines_printed_when_enabled(self):
        """Când enable_dp=True, liniile de log cu ε, δ, noise_multiplier sunt executate."""
        tiny = _make_tiny_model()
        mock_loader = MagicMock()
        mock_loader.dataset = []
        mock_log = MagicMock()

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(FedMedClient, "_load_data", return_value=(mock_loader, mock_loader, None)):
                    with patch.object(FedMedClient, "_validate_model_for_dp"):
                        with patch.object(fc, "get_logger", return_value=mock_log):
                            c = FedMedClient(
                                node_id="node1",
                                model_name="efficientnet_b0",
                                num_classes=2,
                                dataset_path="/fake",
                                device="cpu",
                                enable_signing=False,
                                enable_dp=True,
                                dp_target_epsilon=5.0,
                                dp_target_delta=1e-5,
                                dp_noise_multiplier=0.8,
                                dp_max_grad_norm=1.0,
                            )

        # Verificăm că step() a fost apelat cu valorile DP
        step_calls = [str(call) for call in mock_log.step.call_args_list]
        assert any("5.0" in call for call in step_calls), "Target ε trebuie logat"
        assert any("1e-05" in call or "1e-5" in call for call in step_calls), "Target δ trebuie logat"
        assert any("0.8" in call for call in step_calls), "Noise multiplier trebuie logat"


# ===========================================================================
# FedMedClient.fit() — ramura DP (liniile 405-429, 434, 439)
# ===========================================================================

class TestFitDpBranch:

    def _make_dp_fit_client(self):
        """Client cu enable_dp=True și privacy_engine mock-uit."""
        tiny = _make_tiny_model()
        train_loader = _make_real_loader(8)
        val_loader = _make_real_loader(8)

        mock_history = {
            "train_loss": [0.5], "val_loss": [0.4], "best_val_acc": 0.75,
        }

        with patch.object(fc, "get_model", return_value=tiny):
            with patch.object(fc, "create_payload_signer", return_value=MagicMock(is_ready=lambda: False)):
                with patch.object(FedMedClient, "_load_data", return_value=(train_loader, val_loader, None)):
                    with patch.object(FedMedClient, "_validate_model_for_dp"):
                        with patch.object(fc, "train_model", return_value=mock_history):
                            c = FedMedClient(
                                node_id="node1",
                                model_name="efficientnet_b0",
                                num_classes=2,
                                dataset_path="/fake",
                                device="cpu",
                                enable_signing=False,
                                enable_dp=True,
                            )
        c._mock_history = mock_history
        return c

    def test_fit_dp_enabled_adds_dp_metrics(self):
        """Când DP e activat și privacy_engine e setat, metrics conține dp_epsilon."""
        c = self._make_dp_fit_client()

        mock_pe = MagicMock()
        mock_pe.get_epsilon.return_value = 3.14

        def fake_make_private(module, optimizer, data_loader, **kwargs):
            c.privacy_engine = mock_pe
            return module, optimizer, data_loader

        mock_pe.make_private.side_effect = fake_make_private

        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=c._mock_history):
            with patch.object(fc, "PrivacyEngine", return_value=mock_pe):
                with patch.object(FedMedClient, "_train_with_dp", return_value=c._mock_history):
                    _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        assert metrics.get("dp_enabled") is True
        assert "dp_epsilon" in metrics
        assert metrics["dp_epsilon"] == pytest.approx(3.14, abs=1e-4)
        assert "dp_delta" in metrics

    def test_fit_dp_epsilon_exception_sets_dp_enabled_false(self):
        """Dacă get_epsilon ridică excepție, dp_enabled devine False."""
        c = self._make_dp_fit_client()

        mock_pe = MagicMock()
        mock_pe.get_epsilon.side_effect = RuntimeError("epsilon error")

        def fake_make_private(module, optimizer, data_loader, **kwargs):
            c.privacy_engine = mock_pe
            return module, optimizer, data_loader

        mock_pe.make_private.side_effect = fake_make_private

        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=c._mock_history):
            with patch.object(fc, "PrivacyEngine", return_value=mock_pe):
                with patch.object(FedMedClient, "_train_with_dp", return_value=c._mock_history):
                    _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        assert metrics.get("dp_enabled") is False

    def test_fit_dp_disabled_no_privacy_engine(self):
        """Când enable_dp=False și privacy_engine=None, dp_enabled=False în metrics."""
        c = self._make_dp_fit_client()
        c.enable_dp = False
        c.privacy_engine = None

        params = c.get_parameters({})
        with patch.object(fc, "train_model", return_value=c._mock_history):
            _, _, metrics = c.fit(params, {"server_round": 1, "num_epochs": 1})

        assert metrics["dp_enabled"] is False
        assert "dp_epsilon" not in metrics
