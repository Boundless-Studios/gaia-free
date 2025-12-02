"""
Admin endpoints for managing versioned agent prompts

Access control: restricted to super admin emails via Auth0 token verification.
"""

from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from db.src import get_async_db
from gaia_private.prompts.models.db_models import Prompt
from auth.src.models import User
from auth.src.auth0_jwt_verifier import get_auth0_verifier
from gaia_private.prompts.prompt_service import PromptService
from gaia_private.prompts.models import (
    PromptResponse,
    PromptSummaryResponse,
    CreatePromptRequest,
    UpdatePromptRequest,
    TestPromptRequest,
    TestPromptResponse,
)


# Hardcoded super-admin allowlist (same as admin_endpoints.py)
SUPER_ADMIN_EMAILS = {
    "admin@example.com",
    "admin2@example.com",
    "user1@example.com",
    "user2@example.com",
}

security = HTTPBearer(auto_error=True)


async def require_super_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """
    Verify Auth0 token and restrict access to SUPER_ADMIN_EMAILS.

    Returns User object on success.
    """
    token = credentials.credentials if credentials else None
    verifier = get_auth0_verifier()
    if not verifier:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 not configured"
        )

    payload = verifier.verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing email claim"
        )

    if email not in SUPER_ADMIN_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )

    # Get user from database
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {email} not found in database"
        )

    return user


# API Router
router = APIRouter(
    prefix="/api/admin/prompts",
    tags=["admin", "prompts"],
    dependencies=[Depends(require_super_admin)]
)


@router.get("/summary", response_model=List[PromptSummaryResponse])
async def list_prompt_summaries(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all prompt templates with summary information

    Groups prompts by (agent_type, prompt_key) and shows version counts.
    """
    # Build query to get summary data
    query = (
        select(
            Prompt.agent_type,
            Prompt.prompt_key,
            Prompt.category,
            func.max(case((Prompt.is_active == True, Prompt.version_number), else_=None)).label("active_version"),
            func.count(Prompt.prompt_id).label("total_versions"),
            func.max(Prompt.updated_at).label("last_updated")
        )
        .group_by(Prompt.agent_type, Prompt.prompt_key, Prompt.category)
    )

    if category:
        query = query.where(Prompt.category == category)

    result = await db.execute(query)
    rows = result.all()

    return [
        PromptSummaryResponse(
            agent_type=row.agent_type,
            prompt_key=row.prompt_key,
            category=row.category,
            active_version=row.active_version,
            total_versions=row.total_versions,
            last_updated=row.last_updated,
        )
        for row in rows
    ]


@router.get("/versions/{agent_type}/{prompt_key}", response_model=List[PromptResponse])
async def list_prompt_versions(
    agent_type: str,
    prompt_key: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get all versions of a specific prompt

    Returns versions ordered by version number (newest first).
    """
    prompt_service = PromptService(db)
    prompts = await prompt_service.get_prompt_versions(agent_type, prompt_key)

    return [PromptResponse.from_model(p) for p in prompts]


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific prompt by ID"""
    result = await db.execute(select(Prompt).where(Prompt.prompt_id == prompt_id))
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found"
        )

    return PromptResponse.from_model(prompt)


@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    request: CreatePromptRequest,
    user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new prompt or new version of existing prompt

    - If this is the first prompt for (agent_type, prompt_key), creates version 1
    - If versions exist, creates next version number
    - New prompts are created as inactive by default
    """
    # Get highest version number for this agent+key
    result = await db.execute(
        select(func.max(Prompt.version_number))
        .where(
            Prompt.agent_type == request.agent_type,
            Prompt.prompt_key == request.prompt_key
        )
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    # Get parent prompt (most recent version)
    parent_id = None
    if max_version > 0:
        result = await db.execute(
            select(Prompt.prompt_id)
            .where(
                Prompt.agent_type == request.agent_type,
                Prompt.prompt_key == request.prompt_key,
                Prompt.version_number == max_version
            )
        )
        parent_id = result.scalar_one_or_none()

    # Create new prompt
    new_prompt = Prompt(
        prompt_id=uuid4(),
        agent_type=request.agent_type,
        prompt_key=request.prompt_key,
        category=request.category,
        version_number=next_version,
        parent_prompt_id=parent_id,
        prompt_text=request.prompt_text,
        description=request.description,
        is_active=False,  # New prompts start as inactive
        created_by=user.user_id,
    )

    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)

    return PromptResponse.from_model(new_prompt)


@router.post("/{prompt_id}/activate", response_model=PromptResponse)
async def activate_prompt(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_super_admin),
):
    """
    Activate a specific prompt version

    Deactivates all other versions of the same (agent_type, prompt_key)
    and activates the specified version.
    """
    # Get the target prompt
    result = await db.execute(select(Prompt).where(Prompt.prompt_id == prompt_id))
    target_prompt = result.scalar_one_or_none()

    if not target_prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found"
        )

    # Deactivate all other versions of this prompt
    result = await db.execute(
        select(Prompt).where(
            Prompt.agent_type == target_prompt.agent_type,
            Prompt.prompt_key == target_prompt.prompt_key,
            Prompt.is_active == True
        )
    )
    active_prompts = result.scalars().all()

    for prompt in active_prompts:
        prompt.is_active = False

    # Activate target prompt
    target_prompt.is_active = True

    await db.commit()
    await db.refresh(target_prompt)

    # Invalidate cache for this agent type
    prompt_service = PromptService(db)
    await prompt_service.invalidate_cache(target_prompt.agent_type)

    return PromptResponse.from_model(target_prompt)


@router.post("/{prompt_id}/deactivate", response_model=PromptResponse)
async def deactivate_prompt(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_super_admin),
):
    """
    Deactivate a specific prompt version

    Warning: If you deactivate the only active version, agents will fall back
    to hardcoded prompts until a new version is activated.
    """
    result = await db.execute(select(Prompt).where(Prompt.prompt_id == prompt_id))
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found"
        )

    prompt.is_active = False
    await db.commit()
    await db.refresh(prompt)

    # Invalidate cache
    prompt_service = PromptService(db)
    await prompt_service.invalidate_cache(prompt.agent_type)

    return PromptResponse.from_model(prompt)


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_super_admin),
):
    """
    Delete a prompt version

    Warning: Cannot delete active prompts unless it's the only version.
    If this is the last version of a prompt, deletion is allowed even if active.
    """
    result = await db.execute(select(Prompt).where(Prompt.prompt_id == prompt_id))
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found"
        )

    if prompt.is_active:
        # Check if there are other versions of this prompt
        count_result = await db.execute(
            select(func.count(Prompt.prompt_id))
            .where(
                Prompt.agent_type == prompt.agent_type,
                Prompt.prompt_key == prompt.prompt_key,
                Prompt.prompt_id != prompt_id
            )
        )
        other_versions_count = count_result.scalar()

        # Only block deletion if there are other versions available
        if other_versions_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete active prompt. Deactivate first."
            )

    await db.delete(prompt)
    await db.commit()


@router.post("/{prompt_id}/test", response_model=TestPromptResponse)
async def test_prompt(
    prompt_id: UUID,
    request: TestPromptRequest,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_super_admin),
):
    """
    Test a prompt with sample input using the agent

    This endpoint allows testing a prompt before activating it.
    It runs the prompt through the actual agent and returns the response.

    Args:
        prompt_id: ID of the prompt version to test
        request: Test input and optional context variables
    """
    from gaia.infra.llm.agent_runner import AgentRunner
    from agents import Agent

    # Get the prompt
    result = await db.execute(select(Prompt).where(Prompt.prompt_id == prompt_id))
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt {prompt_id} not found"
        )

    # Render the prompt with context if provided
    rendered_prompt = prompt.prompt_text
    if request.context:
        try:
            rendered_prompt = prompt.prompt_text.format(**request.context)
        except KeyError as e:
            return TestPromptResponse(
                prompt_version=prompt.version_number,
                test_input=request.test_input,
                rendered_prompt=prompt.prompt_text,
                agent_response=None,
                error=f"Missing context variable: {e}"
            )

    try:
        # Create a temporary agent with this prompt
        test_agent = Agent(
            name=f"test_{prompt.agent_type}_{prompt.prompt_key}",
            instructions=rendered_prompt,
            model="gpt-4o",  # Default model for testing
        )

        # Run the agent with test input
        agent_runner = AgentRunner()
        response = await agent_runner.run(
            agent=test_agent,
            input_text=request.test_input
        )

        return TestPromptResponse(
            prompt_version=prompt.version_number,
            test_input=request.test_input,
            rendered_prompt=rendered_prompt,
            agent_response=response.get("response", str(response)),
            error=None
        )

    except Exception as e:
        return TestPromptResponse(
            prompt_version=prompt.version_number,
            test_input=request.test_input,
            rendered_prompt=rendered_prompt,
            agent_response=None,
            error=str(e)
        )
