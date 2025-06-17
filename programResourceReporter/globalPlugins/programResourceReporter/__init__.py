# Program Resource Reporter addon for NVDA
# Copyright (C) 2024-2025
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.

"""Program Resource Reporter addon for NVDA.

Provides detailed CPU and RAM usage information for focused applications.
All scripts support speak on demand mode for compatibility with NVDA 2024.1+.

Version: 2.2.0
Author: Justin
Minimum NVDA version: 2024.1.0
"""

import globalPluginHandler
import ui
import addonHandler
import threading
from typing import List, Optional
import psutil
from scriptHandler import script
from logHandler import log

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
from enum import Enum

class MetricType(Enum):
    """Types of metrics that can be reported."""
    RAM = "ram"
    CPU_PER_CORE = "cpu_per_core"
    CPU_AVERAGE = "cpu_average"

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
            # Don't let errors in child process retrieval crash the addon
            pass
        
        # Return only valid processes
        return [p for p in processes if is_valid_process(p)]

    def _report_metric(self, metric_type: MetricType) -> None:
        """Common method to report resource metrics.
        
        Args:
            metric_type: The type of metric to report
        """
        with self._script_lock:
            try:
                program_name, process = get_focused_process()
                if not program_name:
                    ui.message(_(ERROR_NO_PROCESS))
                    return
                
                processes = self.get_all_processes()
                if not processes:
                    ui.message(_(ERROR_NO_PROCESS))
                    return
                
                # Calculate the metric based on type
                if metric_type == MetricType.RAM:
                    message = self._calculate_ram_usage(program_name, processes)
                elif metric_type == MetricType.CPU_PER_CORE:
                    message = self._calculate_cpu_per_core(program_name, processes)
                elif metric_type == MetricType.CPU_AVERAGE:
                    message = self._calculate_cpu_average(program_name, processes)
                else:
                    return
                    
                if message:
                    ui.message(message)
                else:
                    ui.message(_(ERROR_PROCESS_ENDED))
                    
            except psutil.AccessDenied:
                ui.message(_(ERROR_ACCESS_DENIED))
            except Exception as e:
                log.error(f"Error in _report_metric for {metric_type.value}: {e}", exc_info=True)
                ui.message(_(ERROR_GENERAL))

    def _calculate_ram_usage(self, program_name: str, processes: List[psutil.Process]) -> Optional[str]:
        """Calculate total RAM usage for processes."""
        total_ram = 0
        for p in processes:
            try:
                with p.oneshot():
                    total_ram += p.memory_info().rss
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            except Exception:
                # Specific psutil exceptions are handled above
                # This catches unexpected errors to prevent addon crash
                continue
        
        if total_ram > 0:
            return _("{} is using {} of physical ram").format(
                program_name,
                format_size(total_ram)
            )
        return None

    def _get_combined_cpu_usage(self, processes: List[psutil.Process]) -> List[float]:
        """Get combined CPU usage across all processes."""
        all_cores_usage = []
        for p in processes:
            try:
                per_core = get_process_cpu_per_core(p)
                if not all_cores_usage:
                    all_cores_usage = per_core[:]
                else:
                    # Extend list if needed (more efficient than while loop)
                    if len(per_core) > len(all_cores_usage):
                        all_cores_usage.extend([0.0] * (len(per_core) - len(all_cores_usage)))
                    
                    # Add usage values, capping at 100%
                    for i, usage in enumerate(per_core):
                        if i < len(all_cores_usage):
                            all_cores_usage[i] = min(100, all_cores_usage[i] + usage)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
            except Exception:
                # Specific psutil exceptions are handled above
                # This catches unexpected errors to prevent addon crash
                continue
        return all_cores_usage

    def _calculate_cpu_per_core(self, program_name: str, processes: List[psutil.Process]) -> Optional[str]:
        """Calculate CPU usage per core for processes."""
        all_cores_usage = self._get_combined_cpu_usage(processes)
        if all_cores_usage:
            return _("{}, CPU Usage: {}").format(
                program_name,
                format_cpu_cores(all_cores_usage)
            )
        return None

    def _calculate_cpu_average(self, program_name: str, processes: List[psutil.Process]) -> Optional[str]:
        """Calculate average CPU usage for processes."""
        all_cores_usage = self._get_combined_cpu_usage(processes)
        if all_cores_usage:
            avg_cpu = calculate_average_cpu(all_cores_usage)
            return _("{}, Average CPU Usage: {:.1f}%").format(
                program_name,
                avg_cpu
            )
        return None

    @script(
        description=_("Reports physical RAM usage of the current program"),
        gesture="kb:NVDA+shift+0",
        category=SCRCAT_RESOURCE_USAGE,
        speakOnDemand=True
    )
    def script_announceProgramRAMUsage(self, gesture):
        """Report current program's physical RAM usage."""
        self._report_metric(MetricType.RAM)

    @script(
        description=_("Reports CPU usage per core for the current program"),
        gesture="kb:NVDA+shift+9",
        category=SCRCAT_RESOURCE_USAGE,
        speakOnDemand=True
    )
    def script_announceProgramCPUUsage(self, gesture):
        """Report current program's CPU usage per core."""
        self._report_metric(MetricType.CPU_PER_CORE)
                
    @script(
        description=_("Reports average CPU usage for the current program"),
        # No gesture assigned by default so users can customize
        category=SCRCAT_RESOURCE_USAGE,
        speakOnDemand=True
    )
    def script_announceProgramAverageCPUUsage(self, gesture):
        """Report current program's average CPU usage across all cores."""
        self._report_metric(MetricType.CPU_AVERAGE)

    def terminate(self):
        """Clean up when NVDA is shut down.
        
        Ensures proper cleanup of process cache and metrics data
        to prevent memory leaks and resource conflicts.
        """
        try:
            if hasattr(self, '_process_cache') and self._process_cache:
                self._process_cache.clear()
        except Exception as e:
            # Log but don't fail on cleanup errors
            log.debug(f"Error cleaning up process cache: {e}")
        
        try:
            if hasattr(metrics, 'cleanup'):
                metrics.cleanup(0)  # Clean up any remaining metrics
        except Exception as e:
            # Log but don't fail on cleanup errors  
            log.debug(f"Error cleaning up metrics: {e}")
        
        try:
            super().terminate()
        except Exception as e:
            # Ensure parent cleanup always happens
            log.debug(f"Error in parent terminate: {e}")