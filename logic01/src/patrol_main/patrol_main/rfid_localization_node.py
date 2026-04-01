import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
import math

class RFIDLocalizationNode(Node):
    def __init__(self):
        super().__init__('rfid_localization_node')
        
        # GPIO 경고 비활성화
        GPIO.setwarnings(False)
        
        # RFID 리더기 초기화
        self.reader = SimpleMFRC522()
        
        # 좌표 매핑 데이터 (태그 ID -> x, y, yaw)
        self.landmark_map = {
            428801199154: {'x': 0.0, 'y': 0.0, 'yaw': 0.0},        # Home Base (0,0)
            111222333444: {'x': -1.0341, 'y': 1.5040, 'yaw': 0.0}, # Shelf 2 (TAG-A2-002)
            291971004317: {'x': -1.0189, 'y': -0.2340, 'yaw': 0.0}, # Shelf 3 (TAG-B1-003)
            555666777888: {'x': 0.8633, 'y': -0.0053, 'yaw': 0.0}   # Shelf 4 (TAG-B2-004)
        }
        
        # 디바운싱 설정을 위한 쿨타임 관리 (태그 ID -> 마지막 인식 시간)
        self.last_detection_time = {}
        self.cooldown_sec = 3.0
        
        # /initialpose 토픽 발행자 설정
        self.initial_pose_pub = self.create_publisher(
            PoseWithCovarianceStamped, 
            '/initialpose', 
            10
        )
        
        # RFID 리딩 타머 설정 (0.2초 간격)
        self.timer = self.create_timer(0.2, self.read_rfid_callback)
        
        self.get_logger().info('RFID Localization Node (Virtual Landmark) started.')
        self.get_logger().info('Ready to correct AMCL pose using MFRC522 tags.')

    def read_rfid_callback(self):
        try:
            # 비차단 모드로 태그 읽기 시도
            tag_id, text = self.reader.read_no_block()
            
            if tag_id:
                self.process_tag(tag_id)
        except Exception as e:
            self.get_logger().error(f'Error reading RFID: {e}')

    def process_tag(self, tag_id):
        # 1. 매핑된 태그인지 확인
        if tag_id not in self.landmark_map:
            # 매칭되지 않는 태그는 10초에 한 번만 로그 출력
            if tag_id not in self.last_detection_time or (time.time() - self.last_detection_time.get(tag_id, 0) > 10.0):
                self.get_logger().info(f'Unknown Tag Detected: {tag_id}')
                self.last_detection_time[tag_id] = time.time()
            return

        # 2. 디바운싱(쿨타임) 체크
        current_time = time.time()
        if tag_id in self.last_detection_time:
            if (current_time - self.last_detection_time[tag_id]) < self.cooldown_sec:
                return

        # 3. 위치 보정 데이터 생성 및 발행
        self.publish_initial_pose(tag_id)
        
        # 4. 마지막 인식 시간 업데이트
        self.last_detection_time[tag_id] = current_time

    def publish_initial_pose(self, tag_id):
        coords = self.landmark_map[tag_id]
        
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        
        # 위치 설정
        msg.pose.pose.position.x = coords['x']
        msg.pose.pose.position.y = coords['y']
        msg.pose.pose.position.z = 0.0
        
        # 방향 설정 (Yaw -> Quaternion)
        yaw = coords['yaw']
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        
        # 신뢰도(Covariance) 설정: 높은 신뢰도 (작은 분차 값)
        # 6x6 Matrix (x, y, z, roll, pitch, yaw)
        # [0]=x, [7]=y, [35]=yaw 순격 분산
        msg.pose.covariance = [0.0] * 36
        msg.pose.covariance[0] = 0.05   # x 분산 
        msg.pose.covariance[7] = 0.05   # y 분산
        msg.pose.covariance[35] = 0.05  # yaw 분산
        
        # 나머지 값들을 0.01 정도로 설정하여 AMCL에 강한 힌트 제공
        for i in [14, 21, 28]: # z, roll, pitch
             msg.pose.covariance[i] = 0.01 
             
        self.initial_pose_pub.publish(msg)
        self.get_logger().warn(f'--- Landmark Corrected! --- Tag ID: {tag_id} -> Coords: ({coords["x"]}, {coords["y"]})')

def main(args=None):
    rclpy.init(args=args)
    node = RFIDLocalizationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard Interrupt (SIGINT)')
    finally:
        GPIO.cleanup()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
