import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import math
import time

class RFIDRobotNode(Node):
    def __init__(self):
        super().__init__('rfid_robot_node')
        
        # GPIO 경고 비활성화
        GPIO.setwarnings(False)
        
        # RFID 리더기 초기화
        self.reader = SimpleMFRC522()
        
        # 태그 ID -> 좌표 매핑 (Hard-coded for standalone use)
        self.landmark_map = {
            428801199154: {'x': 0.6213, 'y': 1.6028, 'yaw': 0.0},  # Shelf 1
            291971004317: {'x': -1.0189, 'y': -0.2340, 'yaw': 0.0}  # Shelf 3
        }
        
        self.last_detection_time = {}
        self.cooldown_sec = 3.0
        
        # /initialpose 토픽 발행자
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, 
            '/initialpose', 
            10
        )
        
        # RFID 리딩 타이머 (0.2초 간격)
        self.timer = self.create_timer(0.2, self.read_rfid_callback)
        
        self.get_logger().info('--- Standalone RFID Node for TB3 Started ---')
        self.get_logger().info('No build required. Running directly on hardware.')

    def read_rfid_callback(self):
        try:
            tag_id, text = self.reader.read_no_block()
            if tag_id and tag_id in self.landmark_map:
                curr = time.time()
                if curr - self.last_detection_time.get(tag_id, 0) > self.cooldown_sec:
                    self.publish_pose(tag_id)
                    self.last_detection_time[tag_id] = curr
        except Exception as e:
            self.get_logger().error(f'Error: {e}')

    def publish_pose(self, tag_id):
        c = self.landmark_map[tag_id]
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        msg.pose.pose.position.x = c['x']
        msg.pose.pose.position.y = c['y']
        msg.pose.pose.orientation.z = math.sin(c['yaw'] / 2.0)
        msg.pose.pose.orientation.w = math.cos(c['yaw'] / 2.0)
        
        # 높은 신뢰도 설정 (낮은 공분산)
        msg.pose.covariance = [0.0] * 36
        msg.pose.covariance[0] = 0.05   # x
        msg.pose.covariance[7] = 0.05   # y
        msg.pose.covariance[35] = 0.05  # yaw
        
        self.initial_pose_pub.publish(msg)
        self.get_logger().warn(f'Landmark Corrected! Tag ID: {tag_id} -> Coords: ({c["x"]}, {c["y"]})')

def main(args=None):
    rclpy.init(args=args)
    node = RFIDRobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Exiting...')
    finally:
        GPIO.cleanup()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
