import asyncio
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException

from api.src.socket.websocket_manager import WebSocketManager
from api.src.utils.auth import verify_request
from api.src.utils.models import TopAgentHotkey
from loggers.logging_utils import get_logger
from api.src.backend.queries.agents import get_top_agent, ban_agent as db_ban_agent, approve_agent_version

load_dotenv()

logger = get_logger(__name__)

async def tell_validators_to_set_weights():
    """Tell validators to set their weights."""
    top_agent = await weight_receiving_agent()
    if not top_agent:
        logger.info("No top agent found, skipping weight update")
        return
    
    await WebSocketManager.get_instance().send_to_all_validators("set-weights", top_agent.model_dump(mode='json'))
    
    logger.info(f"Sent updated top agent to all validators: {top_agent.miner_hotkey}")

async def run_weight_setting_loop(minutes: int):
    while True:
        await tell_validators_to_set_weights()
        await asyncio.sleep(minutes * 60)

## Actual endpoints ##

async def weight_receiving_agent():
    '''
    This is used to compute the current best agent. Validators can rely on this or keep a local database to compute this themselves.
    The method looks at the highest scored agents that have been considered by at least two validators. If they are within 3% of each other, it returns the oldest one
    This will be deprecated shortly in favor of validators posting weight themselves
    ''' 
    top_agent: TopAgentHotkey = await get_top_agent()

    return top_agent

async def ban_agent(agent_id: str, ban_password: str):
    if ban_password != os.getenv("BAN_PASSWORD"):
        raise HTTPException(status_code=401, detail="Invalid ban password. Fuck you.")

    try:
        await db_ban_agent(agent_id)
        return {"message": "Agent banned successfully"}
    except Exception as e:
        logger.error(f"Error banning agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to ban agent due to internal server error. Please try again later.")
    

async def trigger_weight_set():
    await tell_validators_to_set_weights()
    return {"message": "Successfully triggered weight update"}

async def approve_version(version_id: str, approval_password: str):
    """Approve a version ID for weight consideration"""
    if approval_password != os.getenv("APPROVAL_PASSWORD"):
        raise HTTPException(status_code=401, detail="Invalid approval password. fucker")

    try:
        await approve_agent_version(version_id)
        return {"message": f"Successfully approved {version_id}"}
    except Exception as e:
        logger.error(f"Error approving version {version_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve version due to internal server error. Please try again later.")

async def re_eval_approved(approval_password: str):
    """
    Re-evaluate approved agents with the newest evaluation set
    by setting the miner_agents status to "awaiting_screening"
    """
    if approval_password != os.getenv("APPROVAL_PASSWORD"):
        raise HTTPException(status_code=401, detail="Invalid approval password")
    
    try:
        logger.info("Starting re-evaluation of approved agents")
        
        # Use state machine to handle the entire re-evaluation flow
        from api.src.backend.agent_machine import AgentStateMachine
        state_machine = AgentStateMachine.get_instance()
        
        agents_to_re_evaluate = await state_machine.re_evaluate_approved_agents()
        
        if not agents_to_re_evaluate:
            logger.info("No approved agents found for re-evaluation")
            return {"message": "No approved agents found for re-evaluation", "agents": []}
        
        logger.info(f"Successfully initiated re-evaluation for {len(agents_to_re_evaluate)} approved agents")
        return {
            "message": f"Successfully initiated re-evaluation for {len(agents_to_re_evaluate)} approved agents",
            "agents": [agent.model_dump(mode='json') for agent in agents_to_re_evaluate]
        }

    except Exception as e:
        logger.error(f"Error re-evaluating approved agents: {e}")
        raise HTTPException(status_code=500, detail="Error initiating re-evaluation of approved agents")
    
router = APIRouter()

routes = [
    ("/check-top-agent", weight_receiving_agent, ["GET"]),
    ("/ban-agent", ban_agent, ["POST"]),
    ("/approve-version", approve_version, ["POST"]),
    ("/trigger-weight-update", trigger_weight_set, ["POST"]),
    ("/re-eval-approved", re_eval_approved, ["POST"])
]

for path, endpoint, methods in routes:
    router.add_api_route(
        path,
        endpoint,
        tags=["scoring"],
        dependencies=[Depends(verify_request)],
        methods=methods
    )
