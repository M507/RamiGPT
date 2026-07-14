import logging
from datetime import datetime, timedelta
import os

# Configure loggers
def setup_logger(name, file, level, format):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.FileHandler(file)
    handler.setLevel(level)
    formatter = logging.Formatter(format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

time_logger = setup_logger('TimeLogger', 'times.log', logging.INFO, '%(asctime)s - %(message)s')
debug_logger = setup_logger('DebugLogger', 'debug.log', logging.DEBUG, '%(asctime)s %(levelname)s:%(message)s')

# Markdown table manager class
class MarkdownTableLogger:
    table_file = "README.md"

    @staticmethod
    def append_to_table(custom_message, start_time, end_time, elapsed_time):
        row = f"| {custom_message} | Link | {start_time} | {end_time} | {elapsed_time} |\n"
        if not os.path.exists(MarkdownTableLogger.table_file):
            content = "# RamiGPT\n\nThis is a tool.\n\n## Timing Table\n\n| Task Description | Start Time | End Time | Elapsed Time |\n|------------------|------------|----------|--------------|\n"
            with open(MarkdownTableLogger.table_file, 'w') as file:
                file.write(content + row)
            return

        with open(MarkdownTableLogger.table_file, 'r+') as file:
            content = file.readlines()
            timing_table_index = -1
            for i, line in enumerate(content):
                if "## Timing Table" in line:
                    timing_table_index = i + 2  # Finding headers
                    while timing_table_index < len(content) and "|" in content[timing_table_index]:
                        timing_table_index += 1
                    break

            if timing_table_index == -1:
                # Timing table section not found, create it at the end of the file
                content.append("\n## Timing Table\n")
                content.append("| Task Description | Link | Start Time | End Time | Elapsed Time |\n")
                content.append("|------------------|------------|------------|----------|--------------|\n")
                content.append(row)
            else:
                # Correctly insert the new row under the last row of the table
                content.insert(timing_table_index, row)
            
            file.seek(0)
            file.writelines(content)
            file.truncate()

# Global timer class
class GlobalTimer:
    start_time = None

    @staticmethod
    def start():
        GlobalTimer.start_time = datetime.now()
        debug_logger.debug("Timer started.")

    @staticmethod
    def stop(custom_message):
        if GlobalTimer.start_time is None:
            debug_logger.error("Timer has not been started.")
            return
        
        end_time = datetime.now()
        elapsed_time = end_time - GlobalTimer.start_time
        time_logger.info(f"{custom_message} - Start Time: {GlobalTimer.start_time}, End Time: {end_time}, Elapsed Time: {elapsed_time}")
        debug_logger.debug(f"Timer stopped. {custom_message} - Elapsed Time: {elapsed_time}")

        # Log to Markdown table
        MarkdownTableLogger.append_to_table(custom_message, GlobalTimer.start_time, end_time, elapsed_time)
        GlobalTimer.start_time = None

