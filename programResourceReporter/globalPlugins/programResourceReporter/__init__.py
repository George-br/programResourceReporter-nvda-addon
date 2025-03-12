"""Program Resource Reporter addon for NVDA.
Provides detailed CPU and RAM usage information for focused applications.
Version: 2.1
"""

import globalPluginHandler
import ui
import addonHandler
import threading
from typing import List
import psutil
from scriptHandler import script

from .process_cache import ProcessCache
from .utils import (
    format_size, 
    get_focused_process, 
    format_cpu_cores, 
    get_process_cpu_per_core,
    is_valid_process,
    metrics,
    calculate_average_cpu
)
from .constants import (
    ERROR_NO_PROCESS,
    ERROR_ACCESS_DENIED,
    ERROR_PROCESS_ENDED,
    ERROR_GENERAL
)

addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """Global plugin for monitoring program resource usage."""
    
    SCRCAT_RESOURCE_USAGE = _("Program Resource Usage")
    
    def __init__(self):
        super().__init__()
        self._process_cache = ProcessCache()
        self._script_lock = threading.Lock()

    def get_all_processes(self) -> List[psutil.Process]:
        """Get all related processes for the focused program."""
        program_name, main_process = get_focused_process()
        if not main_process or not is_valid_process(main_process):
            return []
            
        processes = [main_process]
        try:
            children = self._process_cache.get_child_processes(main_process)
            if children:
                processes.extend(children)
        except Exception:
            pass
        
        # Return only valid processes
        return [p for p in processes if is_valid_process(p)]

    @script(
        description=_("Reports physical RAM usage of the current program"),
        gesture="kb:NVDA+shift+0",
        category=SCRCAT_RESOURCE_USAGE
    )
    def script_announceProgramRAMUsage(self, gesture):
        """Report current program's physical RAM usage."""
        with self._script_lock:
            try:
                program_name, process = get_focused_process()
                if not program_name:
                    ui.message(ERROR_NO_PROCESS)
                    return
                
                total_ram = 0
                for p in self.get_all_processes():
                    try:
                        with p.oneshot():
                            total_ram += p.memory_info().rss
                    except Exception:
                        continue

                if total_ram > 0:
                    message = _("{} is using {} of physical ram").format(
                        program_name,
                        format_size(total_ram)
                    )
                    ui.message(message)
                else:
                    ui.message(ERROR_PROCESS_ENDED)
                
            except psutil.AccessDenied:
                ui.message(ERROR_ACCESS_DENIED)
            except Exception:
                ui.message(ERROR_GENERAL)

    @script(
        description=_("Reports CPU usage per core for the current program"),
        gesture="kb:NVDA+shift+9",
        category=SCRCAT_RESOURCE_USAGE
    )
    def script_announceProgramCPUUsage(self, gesture):
        """Report current program's CPU usage per core."""
        with self._script_lock:
            try:
                program_name, process = get_focused_process()
                if not program_name:
                    ui.message(ERROR_NO_PROCESS)
                    return
                
                processes = self.get_all_processes()
                if not processes:
                    ui.message(ERROR_NO_PROCESS)
                    return
                
                all_cores_usage = []
                for p in processes:
                    per_core = get_process_cpu_per_core(p)
                    if all_cores_usage:
                        while len(all_cores_usage) < len(per_core):
                            all_cores_usage.append(0.0)
                        for i, usage in enumerate(per_core):
                            if i < len(all_cores_usage):
                                all_cores_usage[i] = min(100, all_cores_usage[i] + usage)
                    else:
                        all_cores_usage = per_core[:]
                
                if all_cores_usage:
                    message = _("{}, CPU Usage: {}").format(
                        program_name,
                        format_cpu_cores(all_cores_usage)
                    )
                    ui.message(message)
                else:
                    ui.message(ERROR_PROCESS_ENDED)
                
            except psutil.AccessDenied:
                ui.message(ERROR_ACCESS_DENIED)
            except Exception:
                ui.message(ERROR_GENERAL)
                
    @script(
        description=_("Reports average CPU usage for the current program"),
        # No gesture assigned by default so users can customize
        category=SCRCAT_RESOURCE_USAGE
    )
    def script_announceProgramAverageCPUUsage(self, gesture):
        """Report current program's average CPU usage across all cores."""
        with self._script_lock:
            try:
                program_name, process = get_focused_process()
                if not program_name:
                    ui.message(ERROR_NO_PROCESS)
                    return
                
                processes = self.get_all_processes()
                if not processes:
                    ui.message(ERROR_NO_PROCESS)
                    return
                
                all_cores_usage = []
                for p in processes:
                    per_core = get_process_cpu_per_core(p)
                    if all_cores_usage:
                        while len(all_cores_usage) < len(per_core):
                            all_cores_usage.append(0.0)
                        for i, usage in enumerate(per_core):
                            if i < len(all_cores_usage):
                                all_cores_usage[i] = min(100, all_cores_usage[i] + usage)
                    else:
                        all_cores_usage = per_core[:]
                
                if all_cores_usage:
                    avg_cpu = calculate_average_cpu(all_cores_usage)
                    message = _("{}, Average CPU Usage: {:.1f}%").format(
                        program_name,
                        avg_cpu
                    )
                    ui.message(message)
                else:
                    ui.message(ERROR_PROCESS_ENDED)
                
            except psutil.AccessDenied:
                ui.message(ERROR_ACCESS_DENIED)
            except Exception:
                ui.message(ERROR_GENERAL)

    def terminate(self):
        """Clean up when NVDA is shut down."""
        try:
            if self._process_cache:
                self._process_cache.clear()
            metrics.cleanup(0)  # Clean up any remaining metrics
        except:
            pass
        finally:
            super().terminate()