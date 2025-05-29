from logging.logging_utils import get_logger, logging_update_active_coroutines
from validator.config import DATA_SENDING_INTERVAL, WALLET_NAME, HOTKEY_NAME
import asyncio
import sqlite3
from typing import List, Dict, Any
import aiohttp
from urllib.parse import urljoin
from fiber import constants as cst
from fiber.chain.chain_utils import load_hotkey_keypair

logger = get_logger(__name__)

# API Configuration
API_BASE_URL = "http://localhost:8000"
LOGS_API_ENDPOINT = "/logs"
AVAILABILITY_CHECKS_API_ENDPOINT = "/availability-checks"
CHALLENGE_ASSIGNMENTS_API_ENDPOINT = "/challenge-assignments"
CODEGEN_CHALLENGES_API_ENDPOINT = "/codegen-challenges"
RESPONSES_API_ENDPOINT = "/responses"

def get_validator_hotkey() -> str:
    """Get the validator's hotkey."""
    try:
        keypair = load_hotkey_keypair(WALLET_NAME, HOTKEY_NAME)
        return keypair.ss58_address
    except Exception as e:
        logger.error(f"Failed to load validator hotkey: {str(e)}")
        raise

def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Get a connection to the validator database."""
    return sqlite3.connect(db_path)

def fetch_table_data(table_name: str, db_path: str) -> List[Dict[str, Any]]:
    """
    Fetch all rows from a given table and return them as a list of dictionaries.
    Each dictionary represents a row with column names as keys.
    """
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Fetch all rows
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        result = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Convert any bytes objects to strings
            for key, value in row_dict.items():
                if isinstance(value, bytes):
                    row_dict[key] = value.decode('utf-8')
            result.append(row_dict)
            
        return result
    except Exception as e:
        logger.error(f"Error fetching data from {table_name}: {str(e)}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_logs() -> List[Dict[str, Any]]:
    """Fetch all logs."""
    return fetch_table_data('logs', 'logs.db')

def get_availability_checks() -> List[Dict[str, Any]]:
    """Fetch all availability checks."""
    return fetch_table_data('availability_checks', 'validator.db')

def get_challenge_assignments() -> List[Dict[str, Any]]:
    """Fetch all challenge assignments.""" 
    return fetch_table_data('challenge_assignments', 'validator.db')

def get_codegen_challenges() -> List[Dict[str, Any]]:
    """Fetch all codegen challenges."""
    return fetch_table_data('codegen_challenges', 'validator.db')

def get_responses() -> List[Dict[str, Any]]:
    """Fetch all responses."""
    return fetch_table_data('responses', 'validator.db')

async def send_data_to_api(data: Dict[str, Any], endpoint: str) -> bool:
    """
    Send data to the FastAPI endpoint.
    Returns True if successful, False otherwise.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = urljoin(API_BASE_URL, endpoint)
            headers = {
                cst.VALIDATOR_HOTKEY: get_validator_hotkey()
            }
            async with session.post(url, json=data, headers=headers) as response:
                if response.status == 200:
                    return True
                else:
                    return False
    except Exception as e:
        return False

async def send_data_to_ridges():
    """Run the data sending loop on DATA_SENDING_INTERVAL."""

    while True: 
        logging_update_active_coroutines("data_sending_task", True)
        logger.info("Starting data sending loop")

        # Send logs
        try: 
            logs = get_logs()
            success = await send_data_to_api(logs, LOGS_API_ENDPOINT)
            if success:
                logger.info(f"Logs sent to API successfully")
            else:
                logger.warning("Failed to send logs to API")
        except Exception as e:
            logger.error(f"Error sending logs to API: {str(e)}")

        # Send availability checks
        try:
            availability_checks = get_availability_checks()
            success = await send_data_to_api(availability_checks, AVAILABILITY_CHECKS_API_ENDPOINT)
            if success:
                logger.info(f"Availability checks sent to API successfully")
            else:
                logger.warning("Failed to send availability checks to API")
        except Exception as e:
            logger.error(f"Error sending availability checks to API: {str(e)}")

        # Send challenge assignments
        try:
            challenge_assignments = get_challenge_assignments()
            success = await send_data_to_api(challenge_assignments, CHALLENGE_ASSIGNMENTS_API_ENDPOINT)
            if success:
                logger.info(f"Challenge assignments sent to API successfully")
            else:
                logger.warning("Failed to send challenge assignments to API")
        except Exception as e:
            logger.error(f"Error sending challenge assignments to API: {str(e)}")

        # Send codegen challenges
        try:
            codegen_challenges = get_codegen_challenges()
            success = await send_data_to_api(codegen_challenges, CODEGEN_CHALLENGES_API_ENDPOINT)
            if success:
                logger.info(f"Codegen challenges sent to API successfully")
            else:
                logger.warning("Failed to send codegen challenges to API")
        except Exception as e:
            logger.error(f"Error sending codegen challenges to API: {str(e)}")

        # Send responses
        try:
            responses = get_responses()
            success = await send_data_to_api(responses, RESPONSES_API_ENDPOINT)
            if success:
                logger.info(f"Responses sent to API successfully")
            else:
                logger.warning("Failed to send responses to API")
        except Exception as e:
            logger.error(f"Error sending responses to API: {str(e)}")

        # Sleep for DATA_SENDING_INTERVAL
        await asyncio.sleep(DATA_SENDING_INTERVAL.total_seconds())