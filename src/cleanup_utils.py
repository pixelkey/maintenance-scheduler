"""Utility functions for cleaning up old files and logs."""

import os
import re
from datetime import datetime, timedelta
from typing import Any


def cleanup_output_folder(output_dir: str, logger: Any, days: int = 30) -> None:
    """Clean up files in the output directory older than specified days."""
    if not os.path.exists(output_dir):
        logger.warning(f"Output directory {output_dir} does not exist")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    count = 0
    
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        
        # Get item modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
        
        if mtime < cutoff_date:
            try:
                # If it's a directory, remove the entire directory tree
                if os.path.isdir(item_path):
                    import shutil
                    shutil.rmtree(item_path)
                    logger.info(f"Removed old output directory: {item}")
                # If it's a file, remove just the file
                elif os.path.isfile(item_path):
                    os.remove(item_path)
                    logger.info(f"Removed old output file: {item}")
                
                count += 1
            except Exception as e:
                logger.error(f"Failed to remove {item}: {e}")
    
    logger.info(f"Removed {count} old items from output directory")


def cleanup_log_file(log_file: str, logger: Any, days: int = 30) -> None:
    """Clean up entries in log file older than specified days."""
    if not os.path.exists(log_file):
        logger.warning(f"Log file {log_file} does not exist")
        return
        
    cutoff_date = datetime.now() - timedelta(days=days)
    temp_file = log_file + '.tmp'
    count = 0
    kept = 0
    
    try:
        with open(log_file, 'r') as f_in, open(temp_file, 'w') as f_out:
            for line in f_in:
                # Try to parse the date from the log line
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    log_date = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    if log_date >= cutoff_date:
                        f_out.write(line)
                        kept += 1
                    else:
                        count += 1
                else:
                    # If we can't parse the date, keep the line
                    f_out.write(line)
                    kept += 1
        
        # Replace original file with cleaned up version
        os.replace(temp_file, log_file)
        logger.info(f"Removed {count} old entries from log file, kept {kept} entries")
        
    except Exception as e:
        logger.error(f"Failed to clean up log file: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
