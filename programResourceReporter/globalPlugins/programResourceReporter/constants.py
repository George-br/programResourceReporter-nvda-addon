# Program Resource Reporter addon for NVDA
# Copyright (C) 2024-2025
# This file is covered by the GNU General Public License.
# See the file LICENSE for more details.

from typing import List, Tuple

# Size formatting thresholds
SIZE_THRESHOLDS: List[Tuple[int, str]] = [
    (1024 ** 3, 'GB'),
    (1024 ** 2, 'MB'),
    (1024, 'KB'),
    (0, 'bytes')
]

# Time intervals (in seconds)
CACHE_CLEANUP_INTERVAL = 60
CPU_MEASUREMENT_INTERVAL = 0.25

# Error messages - Note: These are translated in the module that imports them
ERROR_NO_PROCESS = "Cannot access program information"
ERROR_ACCESS_DENIED = "Cannot access process (requires administrator privileges)"
ERROR_PROCESS_ENDED = "Program is no longer running"
ERROR_GENERAL = "Cannot get process information"

# Process states
VALID_PROCESS_STATUSES = ['running', 'sleeping', 'disk-sleep', 'waking']