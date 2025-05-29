import logging
import os
import sys
import json
from colorama import Back, Fore, Style
import uuid
import sqlite3

# Global set to store active coroutines
active_coroutines = set()

# Global variable to store evaluation loop number
eval_loop_num = 0

def logging_update_active_coroutines(task_name: str, is_running: bool) -> None:
    """Update the status of a task in the global task_statuses dictionary."""
    global active_coroutines
    if is_running:
        active_coroutines.add(task_name)
    else:
        active_coroutines.discard(task_name)  # Use discard instead of remove to avoid KeyError

def logging_update_eval_loop_num(loop_number) -> None:
    """Update the evaluation loop number."""
    global eval_loop_num
    eval_loop_num = loop_number

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Back.WHITE,
    }

    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            levelname_color = self.COLORS[levelname] + Style.BRIGHT + levelname + Style.RESET_ALL
            record.levelname = levelname_color

        message = super().format(record)

        color = self.COLORS.get(record.levelname, Fore.WHITE)
        message = message.replace("$RESET", Style.RESET_ALL)
        message = message.replace("$BOLD", Style.BRIGHT)
        message = message.replace("$COLOR", color)
        message = message.replace("$BLUE", Fore.BLUE + Style.BRIGHT)

        return message



class DatabaseHandler(logging.Handler):
    def __init__(self, db_path: str, max_rows: int = 1000):
        super().__init__()
        self.db_path = db_path
        self.max_rows = max_rows
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create the logs table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    milliseconds REAL,
                    levelname TEXT,
                    filename TEXT,
                    pathname TEXT,
                    funcName TEXT,
                    lineno INTEGER,
                    message TEXT,
                    active_coroutines TEXT,
                    eval_loop_num INTEGER
                )
            """)
            conn.commit()

    def _cleanup_old_logs(self, conn):
        """Delete oldest logs if we exceed max_rows."""
        conn.execute("""
            DELETE FROM logs 
            WHERE id IN (
                SELECT id FROM logs 
                ORDER BY timestamp ASC, milliseconds ASC 
                LIMIT MAX(0, (SELECT COUNT(*) FROM logs) - ?)
            )
        """, (self.max_rows,))
        conn.commit()

    def emit(self, record):
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Strip ANSI codes from levelname
                levelname = record.levelname
                levelname = levelname.replace('\u001b[32m', '')  # Green
                levelname = levelname.replace('\u001b[33m', '')  # Yellow
                levelname = levelname.replace('\u001b[31m', '')  # Red
                levelname = levelname.replace('\u001b[36m', '')  # Cyan
                levelname = levelname.replace('\u001b[1m', '')   # Bold
                levelname = levelname.replace('\u001b[0m', '')   # Reset
                
                log_json = {
                    "id": str(uuid.uuid4()),
                    "timestamp": record.asctime,
                    "milliseconds": record.msecs,
                    "levelname": levelname,
                    "filename": record.name,
                    "pathname": record.pathname,
                    "funcName": record.funcName,
                    "lineno": record.lineno,
                    "message": record.message,
                    "active_coroutines": json.dumps(list(active_coroutines)),
                    "eval_loop_num": eval_loop_num
                }
                
                conn.execute("""
                    INSERT INTO logs (
                        id, timestamp, milliseconds, levelname, filename, 
                        pathname, funcName, lineno, message, active_coroutines, eval_loop_num
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_json["id"], log_json["timestamp"], log_json["milliseconds"],
                    log_json["levelname"], log_json["filename"], log_json["pathname"],
                    log_json["funcName"], log_json["lineno"], log_json["message"],
                    log_json["active_coroutines"], log_json["eval_loop_num"]
                ))
                
                # Clean up old logs if we exceed max_rows
                self._cleanup_old_logs(conn)
                
                conn.commit()
        except Exception as e:
            print(f"Error writing to database: {e}")

def get_logger(name: str):
    logger = logging.getLogger(name.split(".")[-1])
    mode: str = os.getenv("ENV", "prod").lower()

    logger.setLevel(logging.DEBUG if mode != "prod" else logging.INFO)
    logger.handlers.clear()

    format_string = (
        "$BLUE%(asctime)s.%(msecs)03d$RESET | "
        "$COLOR$BOLD%(levelname)-8s$RESET | "
        "$BLUE%(name)s$RESET:"
        "$BLUE%(funcName)s$RESET:"
        "$BLUE%(lineno)d$RESET - "
        "$COLOR$BOLD%(message)s$RESET"
    )

    colored_formatter = ColoredFormatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(colored_formatter)
    logger.addHandler(console_handler)

    # Add database handler with max 1000 rows
    db_handler = DatabaseHandler("logs.db", max_rows=1000)
    logger.addHandler(db_handler)

    logger.debug(f"Logging mode is {logging.getLevelName(logger.getEffectiveLevel())}")
    return logger
