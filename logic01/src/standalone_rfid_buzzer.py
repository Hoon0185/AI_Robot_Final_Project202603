import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from std_msgs.msg import Bool, String
import json
import datetime
import urllib.request
try:
    from turtlebot3_msgs.msg import Sound
    from turtlebot3_msgs.srv import Sound as SoundSrv
except ImportError:
    Sound = None
    SoundSrv = None
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
            428801199154: {'x': 0.0, 'y': 0.0, 'yaw': 0.0},        # Home Base (Standard Origin)
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

        # --- 추가: 부저 제어 통합 ---
        # PC(UI)에서 보내는 부저 신호를 구독
        self.buzzer_sub = self.create_subscription(
            Bool,
            '/robot_buzzer',
            self.buzzer_callback,
            10
        )
        # 터틀봇3 실제 사운드 인터페이스 (서비스 방식 지원 추가)
        if SoundSrv:
            self.sound_client = self.create_client(SoundSrv, '/sound')
            self.get_logger().info('Buzzer linked via /sound Service.')
        elif Sound:
            self.sound_pub = self.create_publisher(Sound, '/sound', 10)
            self.get_logger().info('Buzzer linked via /sound Topic.')
        else:
            self.get_logger().error('turtlebot3_msgs Sound not found. Buzzer will not work.')

        # --- 추가: PC UI 상태 전송 (Heartbeat 제외 - patrol_node에서 수행) ---
        self.heartbeat_pub = self.create_publisher(Bool, '/robot_heartbeat', 10)
        # self.status_timer = self.create_timer(1.0, self.publish_heartbeat)

        # RFID 태그를 주기적으로 읽기 위한 타이머 추가 (0.5초 간격)
        self.read_timer = self.create_timer(0.5, self.read_rfid_callback)

        self.get_logger().info('--- Standalone RFID & Buzzer Node (v1.0.2) Started ---')
        self.get_logger().info('Robot Heartbeat active on /robot_heartbeat.')

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

    def buzzer_callback(self, msg):
        """PC의 UI 신호를 기본 터틀봇3 사운드 서비스 또는 토픽으로 연결합니다."""
        if not msg.data:
            return  # OFF 신호(False)는 무시

        index = 4  # 4(BUTTON1-삐 소리)
        
        try:
            # 1. 서비스 방식 시도 (가장 확실함)
            if hasattr(self, 'sound_client'):
                if self.sound_client.service_is_ready():
                    req = SoundSrv.Request()
                    req.value = index
                    self.sound_client.call_async(req)
                    self.get_logger().info(f'Buzzer Service Call sent (Index: {index})')
                    return
                else:
                    self.get_logger().warn('Sound service not ready, falling back to topic.')

            # 2. 토픽 방식 폴백
            if hasattr(self, 'sound_pub'):
                sound_msg = Sound()
                sound_msg.value = index
                self.sound_pub.publish(sound_msg)
                self.get_logger().info(f'Buzzer Topic published (Index: {index})')
            else:
                self.get_logger().warn('No sound interface available on robot hardware.')
        except Exception as e:
            self.get_logger().error(f'Error triggering buzzer: {e}')

    def publish_heartbeat(self):
        """PC UI가 로봇이 살아있음을 알 수 있도록 주기적으로 하트비트 토픽 발행 (웹 보고는 제외)"""
        msg = Bool()
        msg.data = True
        self.heartbeat_pub.publish(msg)

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
