"""
Teste unitare pentru services/central/app/main.py

Acoperă:
  - GET /health
  - GET /flower/status
  - POST /api/fl/stop
  - POST /api/fl/start
  - _generate_run_id()
  - _get_flower_process_info() (logica internă)

Strategia de testare:
  - FastAPI TestClient pentru toate endpoint-urile HTTP
  - unittest.mock pentru socket, subprocess, os.kill, os.path, Path
  - Nu pornește niciun proces real, nu ascultă pe niciun port
  - Stub-urile pentru node_core și flwr sunt instalate în conftest.py

Rulare:
    pytest tests/test_central_main.py -v
"""
import json
import os
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Importăm app.main cu cale absolută (evită probleme cu sys.path și __init__.py)
_MAIN_PATH = Path(__file__).parent.parent / "services" / "central" / "app" / "main.py"
_spec = importlib.util.spec_from_file_location("app.main", _MAIN_PATH)
central_main = importlib.util.module_from_spec(_spec)
sys.modules["app.main"] = central_main
_spec.loader.exec_module(central_main)

from fastapi.testclient import TestClient

client = TestClient(central_main.app, raise_server_exceptions=True)

# ===========================================================================
# Fixture helpers
# ===========================================================================

def _patch_flower_not_running():
    """Patch care simulează Flower Server oprit (port închis)."""
    return patch.object(central_main, "check_flower_server_running", return_value=False)


def _patch_flower_running(pid: int = 1234):
    """Patch care simulează Flower Server pornit."""
    return patch.object(
        central_main,
        "_get_flower_process_info",
        return_value={"pid": pid, "command": "python -m app.flower_server"},
    )


def _patch_flower_stopped():
    """Patch care simulează Flower Server oprit."""
    return patch.object(central_main, "_get_flower_process_info", return_value=None)


# ===========================================================================
# GET /health
# ===========================================================================

class TestHealthEndpoint:

    def test_health_returns_200(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert r.status_code == 200

    def test_health_ok_field_true(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert r.json()["ok"] is True

    def test_health_service_name(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert r.json()["service"] == "central-fl-management"

    def test_health_flower_running_false_when_stopped(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert r.json()["flower_server_running"] is False

    def test_health_flower_running_true_when_running(self):
        with _patch_flower_running():
            r = client.get("/health")
        assert r.json()["flower_server_running"] is True

    def test_health_has_timestamp(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert "timestamp" in r.json()

    def test_health_has_storage_path(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert "storage_path" in r.json()

    def test_health_using_flower_field_present(self):
        with _patch_flower_stopped():
            r = client.get("/health")
        assert "using_flower" in r.json()


# ===========================================================================
# GET /flower/status
# ===========================================================================

class TestFlowerStatusEndpoint:

    def test_status_200_when_stopped(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert r.status_code == 200

    def test_status_running_false_when_stopped(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert r.json()["flower_server_running"] is False

    def test_status_stopped_string_when_stopped(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert r.json()["status"] == "stopped"

    def test_status_running_true_when_running(self):
        with _patch_flower_running():
            r = client.get("/flower/status")
        assert r.json()["flower_server_running"] is True

    def test_status_running_string_when_running(self):
        with _patch_flower_running():
            r = client.get("/flower/status")
        assert r.json()["status"] == "running"

    def test_status_has_server_address(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert "flower_server_address" in r.json()

    def test_status_has_protocol_grpc(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert r.json()["protocol"] == "gRPC"

    def test_status_has_message(self):
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        assert "message" in r.json()

    def test_status_includes_pid_when_running(self):
        with _patch_flower_running(pid=9999):
            r = client.get("/flower/status")
        data = r.json()
        assert data["flower_server_running"] is True
        # process info cu pid trebuie inclus în răspuns
        assert "process" in data or "message" in data

    def test_status_message_contains_pid_when_running(self):
        with _patch_flower_running(pid=9999):
            r = client.get("/flower/status")
        assert "9999" in r.json()["message"]

    def test_status_message_no_pid_port_open(self):
        """Când process_info are doar port_open (fără pid), mesajul e generic."""
        with patch.object(
            central_main, "_get_flower_process_info",
            return_value={"port_open": True},
        ):
            r = client.get("/flower/status")
        data = r.json()
        assert data["flower_server_running"] is True
        assert "accepting connections" in data["message"]

    def test_status_message_when_stopped(self):
        """Când serverul e oprit, mesajul conține instrucțiuni de pornire."""
        with _patch_flower_stopped():
            r = client.get("/flower/status")
        data = r.json()
        assert data["flower_server_running"] is False
        assert "message" in data
        assert len(data["message"]) > 0


# ===========================================================================
# POST /api/fl/stop
# ===========================================================================

class TestStopFlServerEndpoint:

    def test_stop_returns_not_running_when_stopped(self):
        with _patch_flower_stopped():
            r = client.post("/api/fl/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "not_running"

    def test_stop_kills_process_when_running(self):
        with _patch_flower_running(pid=5678):
            with patch("os.kill") as mock_kill:
                r = client.post("/api/fl/stop")
        assert r.status_code == 200
        mock_kill.assert_called_once()
        # Primul argument al kill trebuie să fie PID-ul
        assert mock_kill.call_args[0][0] == 5678

    def test_stop_returns_stopped_status_after_kill(self):
        with _patch_flower_running(pid=5678):
            with patch("os.kill"):
                r = client.post("/api/fl/stop")
        assert r.json()["status"] == "stopped"

    def test_stop_handles_process_already_gone(self):
        with _patch_flower_running(pid=5678):
            with patch("os.kill", side_effect=ProcessLookupError):
                r = client.post("/api/fl/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"

    def test_stop_handles_kill_exception(self):
        with _patch_flower_running(pid=5678):
            with patch("os.kill", side_effect=PermissionError("no permission")):
                r = client.post("/api/fl/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_stop_no_pid_returns_unknown(self):
        """Dacă process_info există dar fără pid (ex. port_open=True), returnează unknown."""
        with patch.object(central_main, "_get_flower_process_info", return_value={"port_open": True}):
            r = client.post("/api/fl/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "unknown"


# ===========================================================================
# POST /api/fl/start
# ===========================================================================

class TestStartFlServerEndpoint:

    def _mock_popen(self):
        """Returnează un patch pentru subprocess.Popen care nu pornește nimic."""
        mock_proc = MagicMock()
        return patch("subprocess.Popen", return_value=mock_proc)

    def _mock_open_file(self):
        """Patch pentru open() folosit la crearea fișierului de log."""
        return patch("builtins.open", mock_open())

    def _mock_makedirs(self):
        return patch("os.makedirs")

    def test_start_returns_200(self, tmp_path):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post("/api/fl/start")
        assert r.status_code == 200

    def test_start_returns_started_status(self, tmp_path):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post("/api/fl/start")
        assert r.json()["status"] == "started"

    def test_start_already_running_returns_already_running(self):
        with patch.object(central_main, "check_flower_server_running", return_value=True):
            r = client.post("/api/fl/start")
        assert r.status_code == 200
        assert r.json()["status"] == "already_running"

    def test_start_response_contains_config(self):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post(
                            "/api/fl/start",
                            params={"num_rounds": 5, "model_name": "resnet18"},
                        )
        data = r.json()
        assert "config" in data
        assert data["config"]["num_rounds"] == 5
        assert data["config"]["model_name"] == "resnet18"

    def test_start_config_contains_run_id(self):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post("/api/fl/start")
        assert "run_id" in r.json()["config"]

    def test_start_explicit_run_id_preserved(self):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post(
                            "/api/fl/start",
                            params={"run_id": "my_custom_run_01"},
                        )
        assert r.json()["config"]["run_id"] == "my_custom_run_01"

    def test_start_calls_popen_with_flower_server_module(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post("/api/fl/start")
        assert mock_popen.called
        cmd = mock_popen.call_args[0][0]
        assert "app.flower_server" in cmd

    def test_start_passes_num_rounds_to_cmd(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post("/api/fl/start", params={"num_rounds": 7})
        cmd = mock_popen.call_args[0][0]
        assert "--num-rounds" in cmd
        assert "7" in cmd

    def test_start_passes_aggregation_strategy_to_cmd(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post(
                            "/api/fl/start",
                            params={"aggregation_strategy": "fedavgm"},
                        )
        cmd = mock_popen.call_args[0][0]
        assert "--aggregation-strategy" in cmd
        assert "fedavgm" in cmd

    def test_start_passes_run_id_to_cmd(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post(
                            "/api/fl/start",
                            params={"run_id": "fl_fedavg_effb0_run01"},
                        )
        cmd = mock_popen.call_args[0][0]
        assert "--run-id" in cmd
        assert "fl_fedavg_effb0_run01" in cmd

    def test_start_passes_experiments_dir_to_cmd(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post("/api/fl/start")
        cmd = mock_popen.call_args[0][0]
        assert "--experiments-dir" in cmd

    def test_start_passes_test_global_csv_to_cmd(self):
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post("/api/fl/start")
        cmd = mock_popen.call_args[0][0]
        assert "--test-global-csv" in cmd

    def test_start_default_experiments_dir_becomes_absolute(self):
        """experiments_dir relativ (ex. 'experiments') trebuie convertit la '/experiments'."""
        with _patch_flower_not_running():
            with patch("subprocess.Popen") as mock_popen:
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        client.post(
                            "/api/fl/start",
                            params={"experiments_dir": "experiments"},
                        )
        cmd = mock_popen.call_args[0][0]
        idx = cmd.index("--experiments-dir")
        assert cmd[idx + 1].startswith("/"), (
            f"experiments_dir trebuie să fie absolut, primit: {cmd[idx + 1]}"
        )

    def test_start_aggregation_strategy_in_config_response(self):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post(
                            "/api/fl/start",
                            params={"aggregation_strategy": "fedprox"},
                        )
        assert r.json()["config"]["aggregation_strategy"] == "fedprox"

    def test_start_min_fit_clients_in_config(self):
        with _patch_flower_not_running():
            with self._mock_popen():
                with patch("os.makedirs"):
                    with patch("builtins.open", mock_open()):
                        r = client.post(
                            "/api/fl/start",
                            params={"min_fit_clients": 4},
                        )
        assert r.json()["config"]["min_fit_clients"] == 4


# ===========================================================================
# _generate_run_id()
# ===========================================================================

class TestGenerateRunId:

    def test_format_with_no_existing_dirs(self, tmp_path):
        run_id = central_main._generate_run_id("fedavg", "efficientnet_b0", str(tmp_path))
        assert run_id == "fl_fedavg_efficientnet_b0_run01"

    def test_format_increments_with_existing_dirs(self, tmp_path):
        # Creăm un director existent cu prefixul corect
        (tmp_path / "fl_fedavg_efficientnet_b0_run01").mkdir()
        run_id = central_main._generate_run_id("fedavg", "efficientnet_b0", str(tmp_path))
        assert run_id == "fl_fedavg_efficientnet_b0_run02"

    def test_format_increments_multiple(self, tmp_path):
        for i in range(1, 4):
            (tmp_path / f"fl_fedavg_efficientnet_b0_run{i:02d}").mkdir()
        run_id = central_main._generate_run_id("fedavg", "efficientnet_b0", str(tmp_path))
        assert run_id == "fl_fedavg_efficientnet_b0_run04"

    def test_different_strategies_dont_interfere(self, tmp_path):
        (tmp_path / "fl_fedavg_efficientnet_b0_run01").mkdir()
        run_id = central_main._generate_run_id("fedavgm", "efficientnet_b0", str(tmp_path))
        assert run_id == "fl_fedavgm_efficientnet_b0_run01"

    def test_model_name_special_chars_normalized(self, tmp_path):
        run_id = central_main._generate_run_id("fedavg", "efficientnet-b0", str(tmp_path))
        # cratima și punctul trebuie înlocuite cu underscore
        assert "-" not in run_id
        assert run_id.startswith("fl_fedavg_efficientnet_b0_run")

    def test_nonexistent_experiments_dir(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        run_id = central_main._generate_run_id("fedavg", "resnet18", nonexistent)
        assert run_id == "fl_fedavg_resnet18_run01"

    def test_ignores_files_not_dirs(self, tmp_path):
        # Un fișier cu prefixul corect nu trebuie numărat
        (tmp_path / "fl_fedavg_resnet18_run01").touch()
        run_id = central_main._generate_run_id("fedavg", "resnet18", str(tmp_path))
        assert run_id == "fl_fedavg_resnet18_run01"

    def test_run_id_ends_with_two_digit_number(self, tmp_path):
        run_id = central_main._generate_run_id("fedprox", "densenet121", str(tmp_path))
        # Ultimele 2 caractere trebuie să fie cifre
        suffix = run_id.split("_run")[-1]
        assert suffix.isdigit() and len(suffix) == 2


# ===========================================================================
# _get_flower_process_info() — logica internă
# ===========================================================================

class TestGetFlowerProcessInfo:

    def test_returns_none_when_port_closed(self):
        """Dacă portul e închis, returnează None."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # port închis
            mock_sock_cls.return_value = mock_sock
            result = central_main._get_flower_process_info()
        assert result is None

    def test_returns_none_when_port_open_but_not_flower(self):
        """Port deschis dar procesul nu e Flower → None."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # port deschis
            mock_sock_cls.return_value = mock_sock

            # lsof returnează un PID
            lsof_result = MagicMock(returncode=0, stdout="9999\n")
            # ps returnează un proces care nu e Flower
            ps_result = MagicMock(returncode=0, stdout="nginx -g daemon off\n")

            with patch("subprocess.run", side_effect=[lsof_result, ps_result]):
                result = central_main._get_flower_process_info()

        assert result is None

    def test_returns_dict_with_pid_when_flower_running(self):
        """Port deschis și procesul e Flower → dict cu pid."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            lsof_result = MagicMock(returncode=0, stdout="1234\n")
            ps_result = MagicMock(returncode=0, stdout="python -m app.flower_server\n")

            with patch("subprocess.run", side_effect=[lsof_result, ps_result]):
                result = central_main._get_flower_process_info()

        assert result is not None
        assert result["pid"] == 1234
        assert "flower_server" in result["command"]

    def test_returns_port_open_when_lsof_unavailable(self):
        """lsof nu e disponibil → returnează {'port_open': True}."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            with patch("subprocess.run", side_effect=FileNotFoundError):
                result = central_main._get_flower_process_info()

        assert result is not None
        assert result.get("port_open") is True

    def test_returns_none_when_socket_exception(self):
        """Excepție la socket → None."""
        with patch("socket.socket", side_effect=OSError("network error")):
            result = central_main._get_flower_process_info()
        assert result is None

    def test_returns_none_when_lsof_returns_no_pid(self):
        """lsof returnează cod non-zero sau stdout gol → None."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            lsof_result = MagicMock(returncode=1, stdout="")
            with patch("subprocess.run", return_value=lsof_result):
                result = central_main._get_flower_process_info()

        assert result is None

    def test_returns_none_when_ps_returns_nonzero(self):
        """ps returnează cod non-zero → None."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            lsof_result = MagicMock(returncode=0, stdout="1234\n")
            ps_result = MagicMock(returncode=1, stdout="")
            with patch("subprocess.run", side_effect=[lsof_result, ps_result]):
                result = central_main._get_flower_process_info()

        assert result is None

    def test_returns_none_on_subprocess_timeout(self):
        """TimeoutExpired la subprocess → None (codul tratează explicit acest caz)."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            with patch(
                "subprocess.run",
                side_effect=__import__("subprocess").TimeoutExpired(cmd="lsof", timeout=2),
            ):
                result = central_main._get_flower_process_info()

        assert result is None

    def test_returns_port_open_on_generic_exception(self):
        """Excepție generică la subprocess (nu FileNotFoundError, nu Timeout) → {'port_open': True}."""
        import socket as _socket
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock_cls.return_value = mock_sock

            with patch("subprocess.run", side_effect=RuntimeError("unexpected")):
                result = central_main._get_flower_process_info()

        assert result is not None
        assert result.get("port_open") is True


# ===========================================================================
# check_flower_server_running() — wrapper
# ===========================================================================

class TestCheckFlowerServerRunning:

    def test_returns_false_when_process_info_none(self):
        with patch.object(central_main, "_get_flower_process_info", return_value=None):
            assert central_main.check_flower_server_running() is False

    def test_returns_true_when_process_info_present(self):
        with patch.object(
            central_main, "_get_flower_process_info",
            return_value={"pid": 42, "command": "flower_server.py"},
        ):
            assert central_main.check_flower_server_running() is True

    def test_returns_true_for_port_open_info(self):
        with patch.object(
            central_main, "_get_flower_process_info",
            return_value={"port_open": True},
        ):
            assert central_main.check_flower_server_running() is True
