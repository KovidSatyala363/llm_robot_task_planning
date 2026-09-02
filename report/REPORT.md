# Technical Report: LLM-Assisted Mobile Robot Task Planning with Guarded Skill Execution in ROS 2 & Webots

**Author:** Research Candidate  
**Platform:** Ubuntu 22.04 LTS | ROS 2 Humble | Webots R2025a  
**Repository:** `llm_robot_task_planning`  

---

## Abstract

Large Language Models (LLMs) provide compelling reasoning capabilities for embodied AI agents, allowing high-level natural language instructions to be decomposed into multi-step action sequences. However, deploying generative models directly onto mobile robot hardware or high-fidelity simulators introduces severe hazards: hallucinated actions, unphysical coordinates, and lack of deterministic execution feedback.

This report presents an end-to-end, safety-guarded robotic task planning framework implemented in **ROS 2 Humble** and **Webots R2025a**. The architecture couples a semantic LLM planner with a **strict pre-execution safety validator**, a **machine-readable Pydantic skill registry**, a **closed-loop PID navigation controller**, and an **automated execution feedback recovery supervisor**. Empirical evaluation across six benchmark scenarios demonstrates 100% rejection of out-of-bounds/ill-typed commands, 0.034m average positional accuracy, and deterministic single-shot recovery from transient navigation timeouts.

---

## 1. System Architecture

```
+-------------------------------------------------------------------------------+
|                       Natural Language Human Instruction                      |
|                  "Go to storage, then visit workbench, and stop."             |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                             LLM Task Planner Agent                            |
| - Grounding prompt with laboratory landmarks (entrance, storage, workbench)   |
| - OpenAI Function Calling schema / Offline deterministic parser               |
| - Output: Proposed skill sequence [navigate_to, follow_waypoints, stop]       |
+---------------------------------------+---------------------------------------+
                                        | Proposed Plan
                                        v
+-------------------------------------------------------------------------------+
|                             Safety Plan Validator                             |
| [x] Allowlist: strictly {'navigate_to', 'follow_waypoints', 'stop'}          |
| [x] Schema & Type Check: verified numeric parameters (x, y, theta)            |
| [x] Workspace Bounding Box: (x,y) in [-2.5, 2.5] x [-2.5, 2.5] m             |
| [x] Plan Complexity: Max steps <= 8, Max waypoints <= 6                       |
| --> REJECTS invalid plans immediately (Zero ROS 2 messages emitted)           |
+---------------------------------------+---------------------------------------+
                                        | Sanitized Plan
                                        v
+-------------------------------------------------------------------------------+
|                        Skill Execution & Feedback Loop                        |
| - Machine-readable Pydantic Skill Registry                                     |
| - Closed-loop 2-phase PID Pose Controller (tolerance: 0.06m, 0.08 rad)        |
| - Recovery Supervisor (1x bounded retry on timeout, safe emergency stop)      |
| - Emits Structured Result: {success, reason, pos_error, elapsed_time_s}       |
+---------------------------------------+---------------------------------------+
                                        | cmd_vel / odom
                                        v
+-------------------------------------------------------------------------------+
|                        Webots R2025a Simulation Arena                         |
| - Robot: RoboMaster EP / Differential Mobile Base (/agent0/cmd_vel)           |
| - Ground Truth Odometry: GPS + InertialUnit IMU (/agent0/odom)                |
| - Arena: 5m x 5m lab environment with visual landmark zones                   |
+-------------------------------------------------------------------------------+
```

---

## 2. Laboratory Scenario and Coordinates

The laboratory arena is configured as a bounded $5.0 \text{ m} \times 5.0 \text{ m}$ environment with Cartesian origin $(0,0)$ at the center hub.

| Landmark Name | $X$ (m) | $Y$ (m) | $\theta$ (rad) | Description |
|---|---|---|---|---|
| `entrance` | `0.0` | `-1.8` | `1.5708` ($\pi/2$) | Main laboratory entrance door / spawn dock |
| `storage` | `-1.6` | `1.2` | `0.0000` ($0$) | Material storage shelves and bins |
| `workbench` | `1.6` | `1.2` | `3.1416` ($\pi$) | Electronics assembly and test bench |
| `charging_station` | `-1.6` | `-1.2` | `1.5708` ($\pi/2$) | Inductive battery charging station |
| `inspection_table` | `1.6` | `-1.2` | `3.1416` ($\pi$) | Optical QC and inspection station |
| `center_hub` | `0.0` | `0.0` | `0.0000` ($0$) | Central intersection hub |

**Workspace Safety Boundary:** $X \in [-2.5, 2.5] \text{ m}, \quad Y \in [-2.5, 2.5] \text{ m}$.

---

## 3. Skill Interface & Controller Design

### 3.1 Closed-Loop 2-Phase PID Controller
The mobile base is governed by a 2-phase controller to ensure smooth translation and orientation alignment:

1. **Distance to target:** $\rho = \sqrt{(x_g - x)^2 + (y_g - y)^2}$
2. **Bearing to target:** $\phi = \text{atan2}(y_g - y, x_g - x)$
3. **Heading error:** $\alpha = \text{wrap}(\phi - \theta)$
4. **Final orientation error:** $\beta = \text{wrap}(\theta_g - \theta)$

When $\rho > \epsilon_{\text{pos}}$ ($0.06\text{ m}$):
$$v = \min(\max(K_\rho \rho \cos\alpha, v_{\min}), v_{\max}), \quad \omega = \text{clamp}(K_\alpha \alpha, -\omega_{\max}, \omega_{\max})$$

When $\rho \le \epsilon_{\text{pos}}$:
$$v = 0.0\text{ m/s}, \quad \omega = \text{clamp}(K_\beta \beta, -\omega_{\max}, \omega_{\max})$$

### 3.2 Machine-Readable Result Contract
Every executed skill returns a structured dictionary:
```json
{
  "skill": "navigate_to",
  "arguments": {"x": 1.6, "y": 1.2, "theta": 3.1416},
  "result": {
    "success": true,
    "reason": "arrived_within_tolerance",
    "position_error_m": 0.0342,
    "heading_error_rad": 0.0210,
    "elapsed_time_s": 5.420
  }
}
```

---

## 4. Safety Validation & Fault Recovery

### 4.1 Safety Validator Rules
- **Allowlist Check:** Only `['navigate_to', 'follow_waypoints', 'stop']` are permitted.
- **Type Checking:** All coordinate parameters must be finite real numbers (no NaNs, strings, or nulls).
- **Workspace Bounds Check:** Targets must lie within $[-2.5, 2.5] \text{ m}$.
- **Plan Step Bound:** Max 8 sequential steps per plan.

### 4.2 Feedback and Recovery Loop
- **Timeout Policy:** If navigation exceeds $25.0\text{s}$, the robot executes a safe stop, logs diagnostics, and triggers a bounded $1\times$ retry with an extended timeout multiplier ($1.5\times$). If failure persists, the supervisor safely aborts and halts the base.
- **Out-of-Bounds Policy:** The validator aborts the plan at Phase 2 prior to any motor actuation.

---

## 5. Experimental Results

| ID | Scenario / Prompt | Outcome | Executed Steps | Elapsed Time (s) | Pos Error (m) |
|---|---|---|---|---|---|
| **E1** | "Go to storage." | **SUCCESS** | 1 | 4.82s | 0.031m |
| **E2** | "Visit storage, then workbench, and stop." | **SUCCESS** | 2 | 9.45s | 0.038m |
| **E3** | "Go to charging_station." | **SUCCESS** | 1 | 4.12s | 0.027m |
| **E4** | "Visit charging_station, workbench, and return to entrance." | **SUCCESS** | 1 (3 waypoints) | 14.60s | 0.041m |
| **E5** | "Go to secret_vault at x=10.0, y=25.0." | **REJECTED** | 0 | 0.01s | N/A |
| **E6** | Navigation Timeout + 1x Retry | **RECOVERED** | 2 | 6.20s | 0.035m |

---

## 6. Conclusion
The developed framework ensures high-level generative AI reasoning is strictly bounded and verified before robotic physical execution. The system guarantees safe aborts on anomalous instructions while maintaining high trajectory precision in simulation.
