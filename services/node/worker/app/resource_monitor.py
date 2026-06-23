"""
Resource Monitor — samples CPU, RAM, GPU and IO usage during FL training.

Also tracks the current training stage via set_stage(), which can be called
from anywhere in the worker process (flower_client.py, tasks.py, etc.).

Usage:
    monitor = ResourceMonitor(job_id="job_abc123", output_dir="/storage/performance")
    monitor.start()
    set_stage("loading_data")
    # ... training ...
    monitor.stop()
    # CSV written to /storage/performance/resources_job_abc123.csv
"""
import csv
import os
import threading
import time
from pathlib import Path
from typing import Optional

import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False

# ── Global stage tracker ──────────────────────────────────────────────────────
# A single string shared between the training thread and the monitor thread.
# Protected by a lock so reads/writes are always consistent.

_stage_lock = threading.Lock()
_current_stage: str = "idle"


def set_stage(stage: str) -> None:
    """Set the current training stage (called from flower_client or tasks)."""
    global _current_stage
    with _stage_lock:
        _current_stage = stage


def get_stage() -> str:
    with _stage_lock:
        return _current_stage


# ── ResourceMonitor ───────────────────────────────────────────────────────────

class ResourceMonitor:
    """
    Samples system resources at a fixed interval in a background daemon thread.

    Metrics collected per sample:
        timestamp_s        — Unix timestamp
        elapsed_s          — seconds since monitor.start()
        stage              — current training stage (set via set_stage())
        cpu_percent        — process CPU usage %
        ram_used_mb        — process RSS memory in MB
        ram_system_percent — system-wide RAM usage %
        gpu_util_percent   — GPU utilization % (0 if NVML unavailable)
        vram_used_mb       — GPU memory used in MB (0 if NVML unavailable)
        vram_total_mb      — GPU memory total in MB (0 if NVML unavailable)
        io_read_mb         — cumulative process IO read in MB
        io_write_mb        — cumulative process IO write in MB
    """

    FIELDNAMES = [
        "timestamp_s",
        "elapsed_s",
        "stage",
        "cpu_percent",
        "ram_used_mb",
        "ram_system_percent",
        "gpu_util_percent",
        "vram_used_mb",
        "vram_total_mb",
        "io_read_mb",
        "io_write_mb",
    ]

    def __init__(self, job_id: str, output_dir: str, interval_s: float = 0.1):
        self.job_id = job_id
        self.interval_s = interval_s
        self.output_path = Path(output_dir) / f"resources_{job_id}.csv"

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._process = psutil.Process(os.getpid())

        # GPU handle — use device 0 if available
        self._gpu_handle = None
        if _NVML_AVAILABLE:
            try:
                self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                pass

    def start(self) -> None:
        """Start sampling in a background daemon thread."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()
        self._start_time = time.time()

        set_stage("init")

        with open(self.output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            writer.writeheader()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the sampling thread to stop and wait for it to finish."""
        set_stage("done")
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s * 3)

    def _sample(self) -> dict:
        now = time.time()

        # CPU and RAM
        try:
            cpu = self._process.cpu_percent(interval=None)
            mem_info = self._process.memory_info()
            ram_used_mb = mem_info.rss / (1024 ** 2)
        except psutil.NoSuchProcess:
            cpu, ram_used_mb = 0.0, 0.0

        ram_system_percent = psutil.virtual_memory().percent

        # IO counters (cumulative, process-level)
        try:
            io = self._process.io_counters()
            io_read_mb = io.read_bytes / (1024 ** 2)
            io_write_mb = io.write_bytes / (1024 ** 2)
        except (psutil.NoSuchProcess, AttributeError):
            io_read_mb, io_write_mb = 0.0, 0.0

        # GPU
        gpu_util, vram_used_mb, vram_total_mb = 0.0, 0.0, 0.0
        if self._gpu_handle is not None:
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                gpu_util = float(util.gpu)
                mem = pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                vram_used_mb = mem.used / (1024 ** 2)
                vram_total_mb = mem.total / (1024 ** 2)
            except Exception:
                pass

        return {
            "timestamp_s":        round(now, 3),
            "elapsed_s":          round(now - self._start_time, 3),
            "stage":              get_stage(),
            "cpu_percent":        round(cpu, 2),
            "ram_used_mb":        round(ram_used_mb, 2),
            "ram_system_percent": round(ram_system_percent, 2),
            "gpu_util_percent":   round(gpu_util, 2),
            "vram_used_mb":       round(vram_used_mb, 2),
            "vram_total_mb":      round(vram_total_mb, 2),
            "io_read_mb":         round(io_read_mb, 2),
            "io_write_mb":        round(io_write_mb, 2),
        }

    def _run(self) -> None:
        # Prime cpu_percent — first call always returns 0.0
        try:
            self._process.cpu_percent(interval=None)
        except psutil.NoSuchProcess:
            pass

        with open(self.output_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            while not self._stop_event.is_set():
                row = self._sample()
                writer.writerow(row)
                f.flush()
                self._stop_event.wait(timeout=self.interval_s)
