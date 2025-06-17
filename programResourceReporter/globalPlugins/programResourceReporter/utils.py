# Program Resource Reporter addon for NVDA
# Copyright (C) 2024-2025
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.

import time
import threading
from typing import Optional, Tuple, List
import psutil
import api
from .constants import (
    SIZE_THRESHOLDS,
    CPU_MEASUREMENT_INTERVAL,
    VALID_PROCESS_STATUSES
)

class ProcessMetrics:
    """Thread-safe process metrics handler."""
    
    def __init__(self):
        self._last_cpu_check: dict = {}
        self._lock = threading.Lock()

    def get_cpu_usage(self, process: psutil.Process) -> List[float]:
        """Get CPU usage per core for a process.
        
        Args:
            process: psutil.Process instance
            
        Returns:
            List of CPU usage percentages per core
            
        Raises:
            psutil.AccessDenied: If access to process is denied
            psutil.NoSuchProcess: If process no longer exists
        """
        with self._lock:
            current_time = time.time()
            total_cores = psutil.cpu_count(logical=True) or 1
            pid = process.pid

            # Check throttling
            last_check = self._last_cpu_check.get(pid, 0)
            if current_time - last_check < CPU_MEASUREMENT_INTERVAL:
                return [0.0] * total_cores

            try:
                if not is_valid_process(process):
                    raise psutil.NoSuchProcess(pid)

                self._last_cpu_check[pid] = current_time
                with process.oneshot():
                    cpu_percent = process.cpu_percent(interval=CPU_MEASUREMENT_INTERVAL)
                
                # Initialize and distribute CPU usage
                core_usage = [0.0] * total_cores
                remaining = cpu_percent
                core_index = 0
                
                while remaining > 0 and core_index < total_cores:
                    if remaining >= 100:
                        core_usage[core_index] = 100.0
                        remaining -= 100
                    else:
                        core_usage[core_index] = remaining
                        remaining = 0
                    core_index += 1
                
                return core_usage
                
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                # Re-raise specific psutil exceptions for proper handling upstream
                raise
            except Exception:
                # For any other exception, return zeros
                return [0.0] * total_cores

    def cleanup(self, pid: int):
        """Clean up process data."""
        with self._lock:
            self._last_cpu_check.pop(pid, None)

# Global metrics instance
metrics = ProcessMetrics()

def format_size(bytes_val: int) -> str:
    """Format bytes to human readable size."""
    for threshold, unit in SIZE_THRESHOLDS:
        if bytes_val >= threshold:
            value = bytes_val / (threshold if threshold > 0 else 1)
            return f"{value:.1f} {unit}"
    return f"{bytes_val} bytes"

def is_valid_process(process: psutil.Process) -> bool:
    """Check if process is valid and accessible."""
    try:
        with process.oneshot():
            return (process.is_running() and 
                   process.status() in VALID_PROCESS_STATUSES)
    except Exception:
        return False

def get_focused_process() -> Tuple[Optional[str], Optional[psutil.Process]]:
    """Get the currently focused process."""
    try:
        focus = api.getFocusObject()
        if not focus or not focus.appModule:
            return None, None
        
        process = psutil.Process(focus.appModule.processID)
        if not is_valid_process(process):
            return None, None
        
        with process.oneshot():
            return process.name(), process
    except Exception:
        return None, None

def get_process_cpu_per_core(process: psutil.Process) -> List[float]:
    """Get CPU usage per core for a process.
    
    Args:
        process: psutil.Process instance
        
    Returns:
        List of CPU usage percentages per core
        
    Raises:
        psutil.AccessDenied: If access to process is denied
        psutil.NoSuchProcess: If process no longer exists
    """
    if not is_valid_process(process):
        raise psutil.NoSuchProcess(process.pid)
    return metrics.get_cpu_usage(process)

def format_cpu_cores(per_core_usage: List[float]) -> str:
    """Format CPU usage per core as string."""
    return ", ".join(f"Core {i}: {usage:.1f}%" 
                    for i, usage in enumerate(per_core_usage, 1))

def calculate_average_cpu(per_core_usage: List[float]) -> float:
    """Calculate average CPU usage across all cores.
    
    Args:
        per_core_usage: List of CPU usage percentages per core
        
    Returns:
        Average CPU usage as a percentage (0-100%)
    """
    if not per_core_usage:
        return 0.0
    
    # Simple average of all core usage percentages
    return sum(per_core_usage) / len(per_core_usage)