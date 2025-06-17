# Program Resource Reporter addon for NVDA
# Copyright (C) 2024-2025
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.

import time
import threading
from typing import Dict, List
import psutil
from .constants import CACHE_CLEANUP_INTERVAL
from .utils import is_valid_process, metrics

class ProcessCache:
    """Thread-safe process cache with automatic cleanup."""
    
    def __init__(self):
        self._cache: Dict[int, psutil.Process] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def get_child_processes(self, parent_process: psutil.Process) -> List[psutil.Process]:
        """Get all child processes for a given parent process."""
        if not is_valid_process(parent_process):
            return []
            
        valid_children = []
        try:
            with parent_process.oneshot():
                children = parent_process.children(recursive=True)
                
            with self._lock:
                self._cleanup()  # Perform periodic cleanup
                
                for child in children:
                    try:
                        if is_valid_process(child):
                            pid = child.pid
                            self._cache[pid] = child
                            valid_children.append(child)
                    except Exception:
                        continue
                        
            return valid_children
            
        except Exception:
            return []

    def _remove_process(self, pid: int):
        """Remove a process and clean up its resources."""
        self._cache.pop(pid, None)
        metrics.cleanup(pid)

    def _cleanup(self):
        """Remove stale processes."""
        current_time = time.time()
        if current_time - self._last_cleanup < CACHE_CLEANUP_INTERVAL:
            return

        stale_pids = [
            pid for pid, process in self._cache.items()
            if not is_valid_process(process)
        ]
        
        for pid in stale_pids:
            self._remove_process(pid)
        
        self._last_cleanup = current_time

    def clear(self):
        """Clear all cached processes."""
        with self._lock:
            pids = list(self._cache.keys())
            for pid in pids:
                self._remove_process(pid)
            self._cache.clear()