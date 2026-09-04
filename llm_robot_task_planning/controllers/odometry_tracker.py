import math
from sensor_msgs.msg import NavSatFix, Imu
from geometry_msgs.msg import Pose2D

class OdometryTracker:
    """Tracks robot pose in ENU coordinates using GPS and IMU sensors."""
    def __init__(self):
        self.pose = Pose2D()
        self.has_gps = False
        self.has_imu = False

    def update_gps(self, msg: NavSatFix):
        self.pose.x = float(msg.longitude)
        self.pose.y = float(msg.latitude)
        self.has_gps = True

    def update_imu(self, msg: Imu):
        q = msg.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.pose.theta = math.atan2(siny_cosp, cosy_cosp)
        self.has_imu = True

    @property
    def is_ready(self) -> bool:
        return self.has_gps and self.has_imu
