SKILL_REGISTRY = [
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Move the mobile robot from current pose to target pose (x, y, theta).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "Target X coordinate [-2.3, 2.3]"},
                    "y": {"type": "number", "description": "Target Y coordinate [-2.3, 2.3]"},
                    "theta": {"type": "number", "description": "Target yaw angle [-3.1416, 3.1416]"}
                },
                "required": ["x", "y", "theta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "follow_waypoints",
            "description": "Visit a sequential list of waypoint target poses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "waypoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "theta": {"type": "number"}
                            },
                            "required": ["x", "y", "theta"]
                        }
                    }
                },
                "required": ["waypoints"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Safely halt all robot motion immediately.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]
