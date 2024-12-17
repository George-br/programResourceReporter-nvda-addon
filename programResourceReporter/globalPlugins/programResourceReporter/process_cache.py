import time
import threading
from typing import Optional, Dict, List
import psutil
from .constants import CACHE_CLEANUP_INTERVAL
from .utils import is_valid_process, metrics

class ProcessCache:
    """Thread-safe process cache with automatic cleanup."""
    
    def __init__(self):
        self._cache: Dict[int, psutil.Process] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def get(self, pid: int) -> Optional[psutil.Process]:
        """Get a process from cache or create new one."""
        with self._lock:
            self._cleanup()
            
            # Return cached process if valid
            if pid in self._cache and is_valid_process(self._cache[pid]):
                return self._cache[pid]
            
            # Try to create new process
            try:
                process = psutil.Process(pid)
                if is_valid_process(process):
                    self._cache[pid] = process
                    return process
                return None
            except Exception:
                self._remove_process(pid)
                return None

    def get_child_processes(self, parent_process: psutil.Process) -> List[psutil.Process]:
        """Get all child processes for a given parent process."""
        if not is_valid_process(parent_process):
            return []
            
        valid_children = []
        try:
            with parent_process.oneshot():
                children = parent_process.children(recursive=True)
                
            with self._lock:
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