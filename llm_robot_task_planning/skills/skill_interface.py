from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class NavigateToArgs(BaseModel):
    x: float = Field(..., description="Target X coordinate in meters", ge=-2.3, le=2.3)
    y: float = Field(..., description="Target Y coordinate in meters", ge=-2.3, le=2.3)
    theta: float = Field(0.0, description="Target heading angle in radians", ge=-3.1416, le=3.1416)

class Waypoint(BaseModel):
    x: float
    y: float
    theta: float = 0.0

class FollowWaypointsArgs(BaseModel):
    waypoints: List[Waypoint] = Field(..., min_items=1, description="List of waypoints to follow")

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
