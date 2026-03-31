import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from turtlebot3_msgs.msg import Sound
import subprocess
import os
import signal

class ManualController(Node):
    def __init__(self, use_remote_bringup=False): # 기본값을 False로 두어 로봇 없이도 즉시 실행 가능하게 함
        super().__init__('manual_controller')

        # --- [설정 부분] ---
        self.robot_ip = "192.168.0.XX"
        self.robot_user = "ubuntu"
        self.is_connected = False
        self.bringup_process = None
        # ------------------

        if use_remote_bringup:
            self._start_remote_bringup()
        else:
            # 로봇 연결 없이 개발할 때: 연결된 것으로 간주하고 시뮬레이션 모드 작동
            self.get_logger().info("Running in DEBUG mode (No remote bringup)")
            self.is_connected = True

        # Publisher 설정 (연결 여부와 상관없이 생성해두어야 코드가 에러 없이 돌아감)
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.sound_pub = self.create_publisher(Sound, '/sound', 10)

        self.linear_vel = 0.2
        self.angular_vel = 1.0

    def _start_remote_bringup(self):
        """SSH를 통한 실제 로봇 연결 시도"""
        ssh_command = [
            'ssh', '-o', 'ConnectTimeout=2', # 타임아웃을 2초로 단축
            f'{self.robot_user}@{self.robot_ip}',
            f'export TURTLEBOT3_MODEL=burger && ros2 launch turtlebot3_bringup robot.launch.py'
        ]

        try:
            self.bringup_process = subprocess.Popen(
                ssh_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )

            try:
                # 기동 즉시 종료 여부 확인 (0.5초)
                ret = self.bringup_process.wait(timeout=0.5)
                self.get_logger().error(f"Robot connection failed (Code: {ret})")
                self.is_connected = False
            except subprocess.TimeoutExpired:
                self.get_logger().info(f"Connected to Robot at {self.robot_ip}")
                self.is_connected = True
        except Exception as e:
            self.get_logger().error(f"SSH process error: {e}")
            self.is_connected = False

    def move_robot(self, direction):
        """로봇 이동 명령 (미연결 시 로그만 출력)"""
        if not self.is_connected:
            self.get_logger().warn(f"Offline: {direction} command ignored.")
            return

        msg = Twist()
        if direction == "UP": msg.linear.x = self.linear_vel
        elif direction == "DOWN": msg.linear.x = -self.linear_vel
        elif direction == "LEFT": msg.angular.z = self.angular_vel
        elif direction == "RIGHT": msg.angular.z = -self.angular_vel
        elif direction == "STOP":
            msg.linear.x = 0.0
            msg.angular.z = 0.0

        self.publisher_.publish(msg)
        # 로봇이 없을 때 확인하기 좋게 로그 추가
        if self.bringup_process is None:
            self.get_logger().info(f"[SIM] Publish Twist: {direction}")

    def play_sound(self, sound_type="ON"):
        """터틀봇 부저 제어 (1: ON, 2: ERROR, 0: OFF)"""
        if not self.is_connected:
            return

        sound_map = {"ON": 1, "ERROR": 2, "OFF": 0}
        msg = Sound()
        msg.value = sound_map.get(sound_type, 0)

        self.sound_pub.publish(msg)
        self.get_logger().info(f"Sent sound: {sound_type}")

    def stop_robot(self):
        self.move_robot("STOP")

    def __del__(self):
        if self.bringup_process:
            try:
                if self.bringup_process.poll() is None:
                    os.killpg(os.getpgid(self.bringup_process.pid), signal.SIGTERM)
            except Exception:
                pass
