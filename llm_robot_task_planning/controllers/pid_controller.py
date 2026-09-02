import math

class DifferentialPIDController:
    """Robust Two-Phase Unicycle / Differential PID Controller."""
    def __init__(self, linear_kp: float = 1.0, angular_kp: float = 2.0,
                 max_linear: float = 0.45, max_angular: float = 1.4,
                 pos_tol: float = 0.28, heading_tol: float = 0.30):
        self.kp_lin = linear_kp
        self.kp_ang = angular_kp
        self.max_lin = max_linear
        self.max_ang = max_angular
        self.pos_tol = pos_tol
        self.heading_tol = heading_tol

    @staticmethod
    def normalize_angle(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def compute(self, current_x: float, current_y: float, current_yaw: float,
                target_x: float, target_y: float, target_theta: float) -> tuple[float, float, bool]:
        """Returns (linear_velocity, angular_velocity, is_goal_reached)."""
        dx = target_x - current_x
        dy = target_y - current_y
        dist_err = math.hypot(dx, dy)

        # Phase 1: Drive to 2D target position
        if dist_err > self.pos_tol:
            target_heading = math.atan2(dy, dx)
            heading_err = self.normalize_angle(target_heading - current_yaw)

            if abs(heading_err) > 0.45:
                # Pivot in place first
                lin_vel = 0.0
                ang_vel = max(min(self.kp_ang * heading_err, self.max_ang), -self.max_ang)
            else:
                # Drive forward with proportional steering
                lin_vel = max(min(self.kp_lin * dist_err, self.max_lin), 0.18)
                ang_vel = max(min(self.kp_ang * heading_err, self.max_ang), -self.max_ang)
            return lin_vel, ang_vel, False

        # Phase 2: Align final heading orientation
        final_heading_err = self.normalize_angle(target_theta - current_yaw)
        if abs(final_heading_err) > self.heading_tol:
            lin_vel = 0.0
            ang_vel = max(min(self.kp_ang * final_heading_err, self.max_ang), -self.max_ang)
            return lin_vel, ang_vel, False

        # Phase 3: Goal Reached!
        return 0.0, 0.0, True
