from typing import List, Dict, Any
import asyncio
import sqlite3

import aiohttp
from urllib.parse import urljoin
from fiber import constants as cst
from fiber.chain.chain_utils import load_hotkey_keypair

from validator.utils.logging import get_logger, logging_update_active_coroutines
from validator.config import DATA_SENDING_INTERVAL, WALLET_NAME, HOTKEY_NAME

logger = get_logger(__name__)


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
        logger.error(f"Error sending data to Ridges API: {str(e)}")
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
        logging_update_active_coroutines("data_sending_task", False)
        await asyncio.sleep(DATA_SENDING_INTERVAL.total_seconds())