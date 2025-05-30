from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from miner.utils.git_ops import clone_and_checkout_repo
from miner.utils.patch import generate_patch
import os
import tempfile
import yaml
import subprocess
import shutil
import uuid

class GeneratedRegressionProblem(BaseModel):
    challenge_id: str
    repository_url: str
    commit_hash: Optional[str]
    problem_statement: str
    context_file_paths: Optional[List[str]] = None

router = APIRouter()

@router.post("/challenge")
async def process_ci_regression_challenge(payload: GeneratedRegressionProblem):
    # Step 1: Receive and parse the request
    print(f"Received CI regression challenge: {payload}")
    # Step 2: Clone the repository and checkout the commit (if provided)
    repo_path = clone_and_checkout_repo(payload.repository_url, payload.commit_hash)
    print(f"Cloned repository to: {repo_path}")

    # Use a dedicated subdirectory for SWE-agent repos
    repos_dir = os.path.join(os.getcwd(), "repos")
    os.makedirs(repos_dir, exist_ok=True)

    # Generate a unique repo name for this run to avoid conflicts and leftover state
    unique_id = str(uuid.uuid4())[:8]
    repo_name = f"{os.path.basename(repo_path)}_{unique_id}"
    target_path = os.path.join(repos_dir, repo_name)
    if os.path.exists(target_path):
        shutil.rmtree(target_path)
    shutil.copytree(repo_path, target_path)

    # Clean up any old SWE-agent target directories in the root (e.g., /<unique_repo_name>)
    # This is necessary because SWE-agent (SWE-ReX) tries to copy the repo to /<repo_name> in the root, and fails if it already exists.
    possible_root_target = f"/{repo_name}"
    if os.path.exists(possible_root_target):
        shutil.rmtree(possible_root_target)

    # NOTE: Ideally, SWE-agent should be configurable to use a temp or /app directory for its working/copy target,
    # but this may require changes to SWE-agent itself. For now, we clean up the root to avoid FileExistsError.

    # Pass the relative path from the current working directory
    relative_repo_path = os.path.relpath(target_path, os.getcwd())

    print("repo_path:", repo_path)
    print("repo_name:", repo_name)
    print("target_path:", target_path)
    print("relative_repo_path:", relative_repo_path)
    print("Current working directory:", os.getcwd())
    print("Contents of working directory:", os.listdir(os.getcwd()))
    print("Contents of repos directory:", os.listdir(repos_dir))

    # Step 3: Prepare SWE-agent config YAML
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise HTTPException(status_code=500, detail="Anthropic API key not set in environment")

    swe_config = {
        "agent": {
            "model": {
                "name": "claude-3-7-sonnet-20250219",
                "per_instance_cost_limit": 3.00
            }
        },
        "env": {
            # Use local deployment type to operate directly on the repo in-place.
            # WARNING: With 'local', SWE-agent will operate directly on the repo in-place.
            # This means any changes, deletions, or file corruptions will affect the original repo directory.
            # If multiple runs or processes use the same repo concurrently, or if you want to preserve the original state, this can cause issues.
            # For maximum safety, always copy the repo to a throwaway directory before using 'local'.
            "repo": {
                "path": relative_repo_path
            },
            "deployment": {
                "type": "local"
            }
        },
        "problem_statement": {
            "text": payload.problem_statement
        }
    }
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        yaml.dump(swe_config, f)
        swe_config_path = f.name
    print(f"Generated SWE-agent config at: {swe_config_path}")

    # Step 4: Run SWE-agent as a subprocess with a timeout to control cost
    try:
        # Timeout (in seconds) can be tuned to control max cost (e.g., 600s = 10min)
        result = subprocess.run(
            ["sweagent", "run", "--config", swe_config_path],
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minutes, adjust as needed for cost control
            cwd=os.getcwd()  # Ensures working directory is /app
        )
        print("SWE-agent stdout:", result.stdout)
        print("SWE-agent stderr:", result.stderr)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"SWE-agent failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="SWE-agent timed out (cost cap reached or infinite loop prevented)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running SWE-agent: {str(e)}")

    # Step 5: Generate the patch
    patch = generate_patch(repo_path)

    # Step 6: Return the patch in the response
    return {
        "challenge_id": payload.challenge_id,
        "patch": patch
    } 