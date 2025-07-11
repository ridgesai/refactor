import json
from typing import Dict, Any
from fastapi import WebSocket

from api.src.backend.queries.agents import get_agent_by_version_id
from api.src.backend.queries.evaluations import get_next_evaluation_for_validator

from api.src.utils.logging_utils import get_logger

logger = get_logger(__name__)


async def handle_get_next_evaluation(
    websocket: WebSocket,
    validator_hotkey: str,
    response_json: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle get-next-evaluation message from a validator"""
    
    try:
        logger.debug(f"Attempting to get next evaluation for validator {validator_hotkey}.")
        evaluation = await get_next_evaluation_for_validator(validator_hotkey)
        if evaluation is None:
            logger.debug(f"No next evaluation found for validator {validator_hotkey}.")
            socket_message = {"event": "evaluation"}  # No evaluations available for this validator
            logger.info(f"Informed validator with hotkey {validator_hotkey} that there are no more evaluations available for it.")
        else:
            agent_version = await get_agent_by_version_id(evaluation.version_id)
            logger.debug(f"Found next evaluation for validator {validator_hotkey}. Evaluation ID: {str(evaluation.evaluation_id)}.")
            socket_message = {
                "event": "evaluation",
                "evaluation_id": str(evaluation.evaluation_id),
                "agent_version": agent_version.model_dump(mode='json') if agent_version else None
            }
            logger.info(f"Platform socket will send requested evaluation {socket_message['evaluation_id']} to validator with hotkey {validator_hotkey}")
        
        logger.debug(f"Attempting to send requested evaluation {socket_message['evaluation_id']} to validator with hotkey {validator_hotkey}.")
        await websocket.send_text(json.dumps(socket_message))
        logger.debug(f"Successfully sent requested evaluation {socket_message['evaluation_id']} to validator with hotkey {validator_hotkey}.")

        return socket_message
        
    except Exception as e:
        logger.error(f"Error getting next evaluation for validator {validator_hotkey}: {str(e)}")
        return {"event": "error", "message": "Failed to get next evaluation"} 