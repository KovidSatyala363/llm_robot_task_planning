from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Bounds are enforced by PlanValidator; pydantic only guarantees types
class NavigateToArgs(BaseModel):
    x: float = Field(..., description="Target X coordinate in meters")
    y: float = Field(..., description="Target Y coordinate in meters")
    theta: float = Field(0.0, description="Target heading angle in radians")

class Waypoint(BaseModel):
    x: float
    y: float
    theta: float = 0.0

class FollowWaypointsArgs(BaseModel):
    waypoints: List[Waypoint] = Field(..., min_length=1, description="List of waypoints to follow")

class StopArgs(BaseModel):
    pass

class SkillCall(BaseModel):
    skill: str
    arguments: Dict[str, Any]

class SkillResult(BaseModel):
    skill: str
    success: bool
    reason: str
    position_error_m: float
    elapsed_time_s: float
    waypoint_reached_idx: Optional[int] = None
