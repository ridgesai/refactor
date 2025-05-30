import json
import os

from fiber.logging_utils import get_logger
from fastapi import APIRouter, Depends, Request, HTTPException

from miner.dependancies import blacklist_low_stake, verify_request, get_config
from miner.core.config import Config
from miner.utils.shared import miner_lock
from miner.utils.git_ops import clone_and_checkout_repo
from miner.utils.llm import generate_solution_with_openai
from miner.utils.patch import generate_patch, apply_patch

logger = get_logger(__name__)

HELLO_WORLD_DIFF = """diff --git a/newfolder/main.py b/newfolder/main.py
new file mode 100644
index 0000000..df1dc68
--- /dev/null
+++ b/newfolder/main.py
@@ -0,0 +1 @@
+print('Hello World')
"""


async def process_challenge(
    request: Request,
    config: Config = Depends(get_config)
):
    logger.info("Attempting to acquire miner lock...")
    async with miner_lock:
        logger.info("Miner lock acquired, processing challenge...")
        try:
            challenge_data = await request.json()
            challenge_id = challenge_data.get("challenge_id")
            problem_statement = challenge_data.get("problem_statement")
            dynamic_checklist = challenge_data.get("dynamic_checklist")
            repository = challenge_data.get("repository_name")
            commit_hash = challenge_data.get("commit_hash")

            logger.info(f"Received challenge data: {json.dumps(challenge_data, indent=2)}")
            
            if not problem_statement or not dynamic_checklist:
                raise HTTPException(status_code=400, detail="Incomplete problem provided")
            
            # Check for OpenAI API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OpenAI API key not set in environment")
                raise HTTPException(status_code=500, detail="OpenAI API key not set in environment")

            logger.info(f"Cloning repository {repository} at commit {commit_hash}")
            repo_path = clone_and_checkout_repo(repository, commit_hash)
            logger.info(f"Repository cloned to {repo_path}")
            
            logger.info(f"Processing challenge {challenge_id} with problem statement {problem_statement}")

            # Generate solution using OpenAI (should be a patch/diff)
            logger.info("Generating solution using OpenAI...")
            solution_patch = generate_solution_with_openai(problem_statement, api_key)
            logger.info(f"Generated solution patch: {solution_patch}")

            # Post-process patch: ensure it ends with a single newline, no trailing whitespace, no extra blank lines
            solution_patch = solution_patch.rstrip() + "\n"

            # Validate patch format
            if not solution_patch.strip().startswith("diff --git"):
                logger.error("LLM output is not a valid git diff (patch). Output was: %s", solution_patch)
                raise HTTPException(status_code=500, detail="LLM did not return a valid git diff (patch).")

            # Apply the patch to the repo
            try:
                apply_patch(repo_path, solution_patch)
                logger.info("Patch applied successfully.")
            except Exception as e:
                logger.error(f"Failed to apply patch: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to apply patch: {str(e)}")

            # Generate a git patch of the changes
            patch = generate_patch(repo_path)
            logger.info(f"Generated patch:\n{patch}")

            response = {
                "challenge_id": challenge_id,
                "patch": patch,
            }
            
            logger.info(f"Responded to challenge {challenge_id}")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing soccer challenge: {str(e)}")
            logger.exception("Full error traceback:")
            raise HTTPException(status_code=500, detail=f"Challenge processing error: {str(e)}")
        finally:
            logger.info("Releasing miner lock...")


# Create router with dependencies
router = APIRouter()
router.add_api_route(
    "/challenge",
    process_challenge,
    tags=["codegen"],
    # Commnent out dependencies for testing
    # dependencies=[Depends(verify_request)],
    methods=["POST"],
)