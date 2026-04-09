import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav_msgs.msg import Path
from std_msgs.msg import Bool, String
import copy
from .inventory_db import InventoryDB

# -- Nav2 서비스 통신을 위한 import --
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType

class ObstacleNode(Node):
    def __init__(self):
        super().__init__('obstacle_node')
        self.db = InventoryDB(base_url="http://16.184.56.119/api")

        db_wait_time = 5 
        try:
            config = self.db.get_patrol_config()
            if config:
                db_wait_time = int(config.get('avoidance_wait_time', 5))
                self.get_logger().info(f"[DB] 서버 대기시간 로드 성공: {db_wait_time}초")
            else:
                self.get_logger().warn(f"[DB] 서버 응답 없음: 기본값 {db_wait_time}초 사용")
        except Exception as e:
            self.get_logger().error(f"[DB] 서버 연결 실패: {e}")

        # 파라미터 선언
        self.declare_parameter('current_wait_time', db_wait_time)
        self.declare_parameter('use_obstacle_avoidance', True) 

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        # ---- 구독 및 발행 설정 ----
        self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile)
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.plan_sub = self.create_subscription(Path, '/plan', self.plan_callback, 10)
        self.teleop_sub = self.create_subscription(Twist, '/cmd_vel_teleop', self.teleop_callback, 10)
        self.ai_mode_sub = self.create_subscription(Bool, '/ai_mode_active', self.ai_mode_callback, 10)

        # cmd_vel_obstacle은 Nav2와 메시지가 섞이지 않도록 신중히 발행
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)
        self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10)
        self.pub_ui_log = self.create_publisher(String, 'obstacle_ui_log', 10)

        # ---- 서비스 클라이언트 ----
        self.nav_param_client = self.create_client(SetParameters, '/controller_server/set_parameters')

        # ---- 타이머 설정 (20Hz) ----
        timer_period = 0.05 
        self.timer = self.create_timer(timer_period, self.timer_callback)

        # ---- 상태 변수 초기화 ----
        self.is_blocked = False
        self.is_moving_backward = False
        self.is_rear_blocked = False
        self.is_teleop_active = False
        self.is_front_danger = False
        self.is_ai_mode = False
        
        self.teleop_linear_x = 0.0
        self.teleop_angular_z = 0.0
        
        self.blocked_start_time = None
        self.no_obstacle_start_time = None
        
        # 거리 기준 최적화 (인플레이션 반경 고려)
        self.safe_distance = 0.25 # 정지 기준 거리
        self.clear_distance = 0.35 # 주행 재개 기준 거리
        
        self.current_wait_time = db_wait_time
        self.latest_scan_msg = None

        self.current_linear_velocity = 0.0
        self.current_angular_velocity = 0.0

    def set_nav2_speed(self, max_speed):
        """
        Nav2의 최대 속도를 동적으로 변경 (필요 시 호출)
        """
        if not self.nav_param_client.wait_for_service(timeout_sec=0.1):
            return

        req = SetParameters.Request()
        param = Parameter()
        param.name = 'FollowPath.max_vel_x'
        param.value = ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(max_speed))

        req.parameters = [param]
        self.nav_param_client.call_async(req)
        self.get_logger().info(f'Nav2 속도 변경 시도: {max_speed} m/s')

    def ai_mode_callback(self, msg):
        self.is_ai_mode = msg.data

    def teleop_callback(self, msg):
        """수동 조작 시 장애물 충돌 방지 로직"""
        self.teleop_linear_x = msg.linear.x
        self.teleop_angular_z = msg.angular.z
        
        use_avoidance = self.get_parameter('use_obstacle_avoidance').get_parameter_value().bool_value
        if not use_avoidance:
            self.cmd_vel_pub.publish(msg)
            return

        # 조작 여부 판별
        if abs(self.teleop_linear_x) > 0.001 or abs(self.teleop_angular_z) > 0.001:
            self.is_teleop_active = True
        else:
            self.is_teleop_active = False
            self.is_front_danger = False
            self.cmd_vel_pub.publish(msg)
            return

        if self.latest_scan_msg is None: return

        final_msg = copy.deepcopy(msg)
        num_ranges = len(self.latest_scan_msg.ranges)

        # [수동 전진 방어] 전방 약 30도 범위 감지
        if self.teleop_linear_x > 0.0:
            idx_15 = int(num_ranges * (15 / 360))
            idx_345 = int(num_ranges * (345 / 360))
            front_ranges = self.latest_scan_msg.ranges[0:idx_15] + self.latest_scan_msg.ranges[idx_345:num_ranges]
            valid_ranges = [r for r in front_ranges if 0.1 < r < 0.5]

            if valid_ranges and min(valid_ranges) < self.safe_distance:
                self.is_front_danger = True
                final_msg.linear.x = 0.0 
            else:
                self.is_front_danger = False

        # [수동 후진 방어] 후방 약 60도 범위 감지 (보완 추가)
        elif self.teleop_linear_x < 0.0:
            idx_150 = int(num_ranges * (150 / 360))
            idx_210 = int(num_ranges * (210 / 360))
            rear_ranges = self.latest_scan_msg.ranges[idx_150:idx_210]
            valid_rear = [r for r in rear_ranges if 0.1 < r < 0.5]

            if valid_rear and min(valid_rear) < self.safe_distance:
                self.is_front_danger = True
                final_msg.linear.x = 0.0
            else:
                self.is_front_danger = False

        self.cmd_vel_pub.publish(final_msg)

    def plan_callback(self, msg):
        pass

    def odom_callback(self, msg):
        self.current_linear_velocity = msg.twist.twist.linear.x
        self.current_angular_velocity = msg.twist.twist.angular.z
        self.is_moving_backward = self.current_linear_velocity < -0.01

    def scan_callback(self, msg):
        """자동 주행 중 장애물 감지 로직"""
        self.latest_scan_msg = msg

        if self.is_teleop_active or self.is_ai_mode:
            return

        # 후방 감지 로직 (후진 시 충돌 방지)
        num_ranges = len(msg.ranges)
        idx_150 = int(num_ranges * (150 / 360))
        idx_210 = int(num_ranges * (210 / 360))
        rear_ranges = msg.ranges[idx_150:idx_210]
        valid_rear = [r for r in rear_ranges if 0.1 < r < 0.30]

        if valid_rear and min(valid_rear) < 0.20:
            self.is_rear_blocked = True
            if self.is_moving_backward:
                self.stop_robot()
        else:
            self.is_rear_blocked = False

        # 전방 감지 로직 (협소 구간 통과를 위해 약 20도 범위 설정)
        idx_10 = int(num_ranges * (10 / 360))
        idx_350 = int(num_ranges * (350 / 360))
        front_ranges = msg.ranges[0:idx_10] + msg.ranges[idx_350:num_ranges]
        valid_ranges = [r for r in front_ranges if 0.1 < r < self.safe_distance]

        if len(valid_ranges) > 0:
            if not self.is_blocked:
                self.get_logger().warn('장애물 감지! 대기를 시작합니다.')
                self.is_blocked = True
                self.blocked_start_time = self.get_clock().now()
                # 행동트리에 장애물 감지 상태 발행
                self.obstacle_status_pub.publish(Bool(data=True))
        else:
            if self.is_blocked:
                # 장애물이 사라진 후 안정성을 위해 짧은 시간 대기 후 해제
                if self.no_obstacle_start_time is None:
                    self.no_obstacle_start_time = self.get_clock().now()
                
                dt = (self.get_clock().now() - self.no_obstacle_start_time).nanoseconds / 1e9
                if dt >= 1.0: # 1초간 유지되면 재개
                    self.is_blocked = False
                    self.no_obstacle_start_time = None
                    self.obstacle_status_pub.publish(Bool(data=False))

    def timer_callback(self):
        """블로킹 상태 관리 타이머"""
        if self.is_teleop_active or self.is_ai_mode:
            return

        self.current_wait_time = float(self.get_parameter('current_wait_time').value)

        if self.is_blocked:
            elapsed = (self.get_clock().now() - self.blocked_start_time).nanoseconds / 1e9

            # 대기 시간 동안은 정지 명령만 유지 (강제 후진 로직 제거)
            if elapsed < self.current_wait_time:
                self.stop_robot()
            else:
                # 대기 시간 종료 시 Nav2가 우회 경로를 찾을 수 있도록 상태 해제
                self.get_logger().info('대기 시간 종료. 우회 경로 탐색을 허용합니다.')
                self.is_blocked = False
                self.obstacle_status_pub.publish(Bool(data=False))

    def stop_robot(self):
        """로봇에 정지 명령 발행"""
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0
        self.cmd_vel_pub.publish(msg)

def main(args=None):
    if not rclpy.ok():
        rclpy.init(args=args)
    node = ObstacleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
