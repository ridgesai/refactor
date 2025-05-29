import logging
import os
import sys

from colorama import Back, Fore, Style

from validator.db.operations import DatabaseManager
from validator.config import DB_PATH

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

class LoggingDatabaseHandler(logging.Handler):
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def emit(self, record):
        self.db_manager.create_error_log(record)

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

    # This also spins up a miner copy of validator.db database, but its purely a log drain and so OK
    db_handler = LoggingDatabaseHandler(DatabaseManager(DB_PATH))
    logger.addHandler(db_handler)

    logger.debug(f"Logging mode is {logging.getLevelName(logger.getEffectiveLevel())}")
    return logger
