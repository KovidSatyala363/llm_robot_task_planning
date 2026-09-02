import sys
import select
import termios
import tty
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

msg = """
Control RoboMaster /agent0 with Keyboard:
------------------------------------------
w : forward
x : backward
a : turn left
d : turn right
s / space : emergency stop
CTRL-C : quit
"""

def getKey(settings):
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def main():
    settings = termios.tcgetattr(sys.stdin)
    rclpy.init()
    node = rclpy.create_node('keyboard_twist')
    pub = node.create_publisher(Twist, '/agent0/cmd_vel', 10)

    target_linear = 0.0
    target_angular = 0.0

    print(msg)
    try:
        while True:
            key = getKey(settings)
            if key == 'w':
                target_linear = min(target_linear + 0.1, 0.4)
            elif key == 'x':
                target_linear = max(target_linear - 0.1, -0.4)
            elif key == 'a':
                target_angular = min(target_angular + 0.2, 1.2)
            elif key == 'd':
                target_angular = max(target_angular - 0.2, -1.2)
            elif key == ' ' or key == 's':
                target_linear = 0.0
                target_angular = 0.0
            elif key == '\x03':
                break

            twist = Twist()
            twist.linear.x = target_linear
            twist.angular.z = target_angular
            pub.publish(twist)
    finally:
        pub.publish(Twist())
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
