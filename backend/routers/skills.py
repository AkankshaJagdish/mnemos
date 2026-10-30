"""CRUD and execution endpoints for user-owned reusable skills."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import get_settings
from backend.database import User, get_db
from backend.schemas import SkillCreate, SkillListResponse, SkillRead, SkillRunRequest, SkillRunResponse, SkillUpdate
from backend.services.model_client import ModelClientError, ModelNotConfiguredError
from backend.services.skill_service import create_skill, delete_skill, get_owned_skill, list_skills, run_skill, update_skill

logger = logging.getLogger("mnemos.routers.skills")
router = APIRouter(prefix="/skills", tags=["skills"])


def _ensure_model_configured() -> None:
    if not get_settings().has_nebius_key:
        raise HTTPException(status_code=503, detail="Nebius Token Factory is not configured.")


@router.get("", response_model=SkillListResponse)
def get_skills(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SkillListResponse:
    return SkillListResponse(skills=list_skills(db, user.id))


@router.post("", response_model=SkillRead, status_code=status.HTTP_201_CREATED)
def post_skill(payload: SkillCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SkillRead:
    return SkillRead.model_validate(create_skill(db, user.id, payload))


@router.patch("/{skill_id}", response_model=SkillRead)
def patch_skill(skill_id: int, payload: SkillUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SkillRead:
    skill = get_owned_skill(db, user.id, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found.")
    return SkillRead.model_validate(update_skill(db, skill, payload))


@router.delete("/{skill_id}")
def remove_skill(skill_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, str]:
    skill = get_owned_skill(db, user.id, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found.")
    delete_skill(db, skill)
    return {"status": "ok"}


@router.post("/{skill_id}/run", response_model=SkillRunResponse)
async def execute_skill(skill_id: int, payload: SkillRunRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SkillRunResponse:
    skill = get_owned_skill(db, user.id, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found.")
    _ensure_model_configured()
    try:
        return await run_skill(db, user.id, skill, payload.input, conversation_id=payload.conversation_id)
    except ModelNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelClientError as exc:
        logger.warning("Skill execution failed: %s", exc)
        raise HTTPException(status_code=502, detail="The model could not complete this skill. Check provider configuration and backend logs.") from exc
    except Exception as exc:
        logger.exception("Unexpected skill execution failure")
        raise HTTPException(status_code=500, detail="Skill execution failed unexpectedly.") from exc
