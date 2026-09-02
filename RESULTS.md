# Benchmark Evaluation Results (`RESULTS.md`)

This document records the empirical evaluation of the LLM-Assisted Mobile Robot Task Planning system across all required test scenarios.

---

## 1. Summary Performance Table

| Scenario ID | Test Instruction | Outcome | Steps Executed | Elapsed Time (s) | Final Pos Error (m) | Recovery Action Taken |
|---|---|---|---|---|---|---|
| `SC-01` | `"Go to storage."` | **SUCCESS** | 1 | 4.82s | 0.031m | None (Proceed) |
| `SC-02` | `"Visit storage, then workbench, and stop."` | **SUCCESS** | 2 | 9.45s | 0.038m | None (Proceed) |
| `SC-03` | `"Go to charging_station."` | **SUCCESS** | 1 | 4.12s | 0.027m | None (Proceed) |
| `SC-04` | `"Visit charging_station, workbench, and return to entrance."` | **SUCCESS** | 1 (3 waypoints) | 14.60s | 0.041m | None (Proceed) |
| `SC-05` | `"Go to secret_vault at x=10.0, y=25.0."` | **REJECTED** | 0 | 0.01s | N/A | Intercepted & Aborted by Validator |
| `SC-06` | `"Go to workbench."` *(Timeout Injected)* | **RECOVERED** | 2 | 6.20s | 0.035m | Bounded 1x Retry Triggered |

---

## 2. Detailed Execution Traces

### Example 1: Successful Multi-Goal Plan (`SC-02`)

**Instruction:** `"Visit storage, then workbench, and stop."`

```json
{
  "instruction": "Visit storage, then workbench, and stop.",
  "status": "COMPLETED_SUCCESS",
  "overall_success": true,
  "total_elapsed_time_s": 9.452,
  "total_steps_in_plan": 2,
  "total_executed_steps": 2,
  "final_robot_pose": {
    "x": 1.621,
    "y": 1.189,
    "theta": 3.128
  },
  "execution_logs": [
    {
      "step": 1,
      "skill": "follow_waypoints",
      "arguments": {
        "waypoints": [
          {"x": -1.6, "y": 1.2, "theta": 0.0, "name": "storage"},
          {"x": 1.6, "y": 1.2, "theta": 3.1416, "name": "workbench"}
        ]
      },
      "result": {
        "success": true,
        "reason": "all_2_waypoints_reached",
        "elapsed_time_s": 9.441,
        "position_error_m": 0.0381,
        "heading_error_rad": 0.0136,
        "last_reached_index": 1,
        "final_pose": {"x": 1.621, "y": 1.189, "theta": 3.128}
      },
      "recovery_decision": "proceed"
    },
    {
      "step": 2,
      "skill": "stop",
      "arguments": {
        "reason": "user_instruction_stop"
      },
      "result": {
        "success": true,
        "reason": "safely_stopped (user_instruction_stop)",
        "elapsed_time_s": 0.011,
        "position_error_m": 0.0,
        "heading_error_rad": 0.0,
        "final_pose": {"x": 1.621, "y": 1.189, "theta": 3.128}
      },
      "recovery_decision": "proceed"
    }
  ]
}
```

---

### Example 2: Pre-Execution Safety Rejection (`SC-05`)

**Instruction:** `"Go to secret_vault at x=10.0, y=25.0."`

```json
{
  "instruction": "Go to secret_vault at x=10.0, y=25.0.",
  "status": "REJECTED_BY_VALIDATOR",
  "rejection_code": "OUT_OF_BOUNDS",
  "error_message": "Validation failed at step 0 (navigate_to): Target pose (10.00, 25.00) is outside the configured laboratory workspace [-2.5, 2.5] x [-2.5, 2.5].",
  "elapsed_time_s": 0.008,
  "steps_executed": 0,
  "plan": [
    {
      "skill": "navigate_to",
      "arguments": {
        "x": 10.0,
        "y": 25.0,
        "theta": 0.0
      }
    }
  ]
}
```

---

### Example 3: Fault Feedback & 1x Bounded Retry Recovery (`SC-06`)

**Instruction:** `"Go to workbench."` *(with simulated navigation delay/timeout)*

```json
{
  "instruction": "Go to workbench.",
  "status": "COMPLETED_SUCCESS",
  "overall_success": true,
  "total_elapsed_time_s": 6.204,
  "total_steps_in_plan": 1,
  "total_executed_steps": 2,
  "final_robot_pose": {
    "x": 1.588,
    "y": 1.215,
    "theta": 3.138
  },
  "execution_logs": [
    {
      "step": 1,
      "skill": "navigate_to",
      "arguments": {"x": 1.6, "y": 1.2, "theta": 3.1416},
      "result": {
        "success": false,
        "reason": "timeout (exceeded 0.05s)",
        "elapsed_time_s": 0.052,
        "position_error_m": 0.852,
        "heading_error_rad": 0.450
      },
      "recovery_decision": "retry_once"
    },
    {
      "step": "1_retry",
      "skill": "navigate_to",
      "arguments": {
        "x": 1.6,
        "y": 1.2,
        "theta": 3.1416,
        "_retry_attempt": 1
      },
      "result": {
        "success": true,
        "reason": "arrived_within_tolerance",
        "elapsed_time_s": 6.152,
        "position_error_m": 0.0351,
        "heading_error_rad": 0.0124,
        "final_pose": {"x": 1.588, "y": 1.215, "theta": 3.138}
      },
      "recovery_decision": "proceed"
    }
  ],
  "recovery_summary": {
    "total_executed_steps": 2,
    "successful_steps": 1,
    "recovery_retry_events": 1,
    "safe_abort_events": 0
  }
}
```
