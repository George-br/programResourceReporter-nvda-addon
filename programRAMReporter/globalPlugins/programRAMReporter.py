import globalPluginHandler
import api
import ui
import scriptHandler
import psutil

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    @scriptHandler.script(
        description="Reports the name of the current program and its physical RAM usage.",
        gesture="kb:NVDA+shift+9"
    )
    def script_announceProgramRAMUsage(self, gesture):
        try:
            focus = api.getFocusObject()
            if not focus or not focus.appModule:
                ui.message("Unable to get program information")
                return
            
            # Get the main process
            process = psutil.Process(focus.appModule.processID)
            program_name = process.name()
            
            # Get physical memory (RSS is most reliable for physical memory)
            total_physical = process.memory_info().rss
            
            def format_size(bytes_val):
                for unit in ['bytes', 'KB', 'MB', 'GB']:
                    if bytes_val < 1024:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024
                return f"{bytes_val:.1f} GB"
            
            message = f"{program_name} is using {format_size(total_physical)} of physical RAM"
            ui.message(message)
            
        except Exception as e:
            ui.message(f"Error: {str(e)}")