"""User profile router."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.deps import supabase, get_current_user
from app.models.core import UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(**current_user)


@router.patch("/me", response_model=UserProfile)
async def update_user_profile(
    updates: dict, current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    response = (
        supabase.table("users").update(updates).eq("id", current_user["id"]).execute()
    )
    if response.data:
        return UserProfile(**response.data[0])
    else:
        raise HTTPException(status_code=404, detail="User not found")
