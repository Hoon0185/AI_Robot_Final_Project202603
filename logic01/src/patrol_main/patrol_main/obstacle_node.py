import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import Path
from std_msgs.msg import Bool, String
import copy
from .inventory_db import InventoryDB

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')

    self.db = InventoryDB()

    # DB에서 대기시간 가져오기
    db_wait_time = 5
    try:
      config = self.db.get_patrol_config()
      if config:
        db_wait_time = int(config.get('avoidance_wait_time', 5))
        self.get_logger().info(f"[DB] 서버 대기시간 로드 성공: {db_wait_time}초")
    except Exception as e:
      self.get_logger().error(f"[DB] 서버 연결 실패: {e}")

    self.declare_parameter('current_wait_time', db_wait_time)
    self.declare_parameter('use_obstacle_avoidance', True) # 런타임 토글 지원

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )

    # 구독/발행 설정
    self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile)
    self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
    self.teleop_sub = self.create_subscription(Twist, '/cmd_vel_teleop', self.teleop_callback, 10)
    self.ai_mode_sub = self.create_subscription(Bool, '/ai_mode_active', self.ai_mode_callback, 10)

    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)
    self.virtual_obstacle_pub = self.create_publisher(LaserScan, '/scan_virtual', 10)
    self.pause_pub = self.create_publisher(Bool, '/pause_patrol', 10)
    self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10)
    self.pub_ui_log = self.create_publisher(String, 'obstacle_ui_log', 10)

    self.clear_costmap_client = self.create_client(ClearEntireCostmap, '/local_costmap/clear_entirely_local_costmap')

    # 타이머 설정 (50Hz)
    self.timer = self.create_timer(0.02, self.timer_callback)

    # 초기 변수
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
    self.safe_distance = 0.50
    self.clear_distance = self.safe_distance + 0.1
    self.current_wait_time = db_wait_time
    self.latest_scan_msg = None
    self.current_linear_velocity = 0.0
    self.current_angular_velocity = 0.0

  def ai_mode_callback(self, msg):
    self.is_ai_mode = msg.data

  def teleop_callback(self, msg):
    """수동조작 시 장애물 감지 및 차단 로직"""
    self.teleop_linear_x = msg.linear.x
    self.teleop_angular_z = msg.angular.z

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

    # 수동 전진 방어 (30도)
    if self.teleop_linear_x > 0.0:
      idx_30 = int(num_ranges * (30 / 360))
      idx_330 = int(num_ranges * (330 / 360))
      front_ranges = self.latest_scan_msg.ranges[0:idx_30] + self.latest_scan_msg.ranges[idx_330:num_ranges]
      valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

      if valid_ranges and min(valid_ranges) < self.safe_distance:
        if not self.is_front_danger:
          self.get_logger().warn(f'[수동] 전방 장애물! 전진 차단 ({min(valid_ranges):.2f}m)')
        final_msg.linear.x = 0.0
        self.is_front_danger = True
      elif valid_ranges and min(valid_ranges) >= self.clear_distance:
        self.is_front_danger = False

    # 수동 후진 방어 (LOGIC_02 최적화)
    elif self.teleop_linear_x < 0.0:
      idx_150 = int(num_ranges * (150 / 360))
      idx_210 = int(num_ranges * (210 / 360))
      rear_ranges = self.latest_scan_msg.ranges[idx_150:idx_210]
      valid_rear = [r for r in rear_ranges if 0.1 < r < 0.5]

      if valid_rear and min(valid_rear) < self.safe_distance:
        if not self.is_front_danger:
          self.get_logger().warn(f'[수동] 후방 장애물! 후진 차단 ({min(valid_rear):.2f}m)')
        final_msg.linear.x = 0.0
        self.is_front_danger = True

    if self.is_front_danger and final_msg.linear.x > 0.0:
      final_msg.linear.x = 0.0

    self.cmd_vel_pub.publish(final_msg)

  def odom_callback(self, msg):
    self.current_linear_velocity = msg.twist.twist.linear.x
    self.is_moving_backward = self.current_linear_velocity < -0.01

  def scan_callback(self, msg):
    """자율 주행 중 장애물 감지 및 우회 경로 생성 보조"""
    self.latest_scan_msg = msg

    # 1. 장애물 회피 기능 활성화 체크
    if not self.get_parameter('use_obstacle_avoidance').get_parameter_value().bool_value:
      return

    # 2. 수동 조작 시에는 콜백 종료 (전용 콜백에서 처리)
    if self.is_teleop_active:
      return

    num_ranges = len(msg.ranges)

    # 3. 후진 중 장애물 감지 (강제 정지)
    idx_120 = int(num_ranges * (120 / 360))
    idx_240 = int(num_ranges * (240 / 360))
    rear_ranges = msg.ranges[idx_120:idx_240]
    valid_rear = [r for r in rear_ranges if 0.1 < r < 0.5]

    if self.is_moving_backward and valid_rear and min(valid_rear) < 0.30:
      self.get_logger().warn('후진 중 장애물 감지! 강제 정지')
      self.stop_robot()
      return

    # 4. AI 모드 중에는 감지 무시
    if self.is_ai_mode:
      return

    # 5. 전방 장애물 감지 (60도 -> 20도 범위 정밀화)
    idx_10 = int(num_ranges * (10 / 360))
    idx_350 = int(num_ranges * (350 / 360))
    front_ranges = msg.ranges[0:idx_10] + msg.ranges[idx_350:num_ranges]
    valid_front = [r for r in front_ranges if 0.1 < r < 0.30]

    if valid_front:
      min_dist = min(valid_front)
      if min_dist < self.safe_distance:
        if not self.is_blocked:
          self.get_logger().warn(f'장애물 발견! 거리: {min_dist:.2f}m')
          self.is_blocked = True
          self.blocked_start_time = self.get_clock().now()
          self.no_obstacle_start_time = None
          self.set_nav2_speed(0.0) # 즉시 정지 요청
          self.obstacle_status_pub.publish(Bool(data=True))

        self.stop_robot()
        self.publish_fake_scan(msg) # 가짜 벽 생성 (Nav2 우회용)
      else:
        self._check_obstacle_clearance()
    else:
      self._check_obstacle_clearance()

  def _check_obstacle_clearance(self):
    """장애물이 사라졌는지 확인하고 속도 복구"""
    if self.is_blocked:
      if self.no_obstacle_start_time is None:
        self.no_obstacle_start_time = self.get_clock().now()
      
      elapsed = (self.get_clock().now() - self.no_obstacle_start_time).nanoseconds / 1e9
      if elapsed >= 1.5:
        self.get_logger().info('장애물 해제됨. 주행 재개')
        self.call_clear_costmap_service()
        self.set_nav2_speed(0.2)
        self.is_blocked = False
        self.obstacle_status_pub.publish(Bool(data=False))
        self.no_obstacle_start_time = None
      else:
        self.stop_robot()

  def timer_callback(self):
    if not self.get_parameter('use_obstacle_avoidance').get_parameter_value().bool_value:
      return
    if self.is_teleop_active or self.is_ai_mode:
      return

    self.current_wait_time = self.get_parameter('current_wait_time').get_parameter_value().integer_value

    # 지정된 대기시간 경과 후 Nav2 자체 우회 시도 허용
    if self.is_blocked:
      elapsed = (self.get_clock().now() - self.blocked_start_time).nanoseconds / 1e9
      if elapsed >= self.current_wait_time:
        self.get_logger().info(f'{self.current_wait_time}초 경과. Nav2 우회 시작')
        self.set_nav2_speed(0.2)
        self.is_blocked = False
        self.blocked_start_time = None
        self.obstacle_status_pub.publish(Bool(data=False))

  def publish_fake_scan(self, msg):
    """Nav2가 장애물을 피해가도록 가짜 벽을 0.6m 지점에 생성"""
    fake_msg = copy.deepcopy(msg)
    num_ranges = len(fake_msg.ranges)
    idx_10 = int(num_ranges * (10 / 360))
    idx_350 = int(num_ranges * (350 / 360))
    for i in range(num_ranges):
      if i < idx_10 or i > idx_350:
        fake_msg.ranges[i] = 0.6
      else:
        fake_msg.ranges[i] = float('inf')
    self.virtual_obstacle_pub.publish(fake_msg)

  def set_nav2_speed(self, speed):
    """Nav2 최대 속도를 조절하여 주행 제어"""
    try:
      from rcl_interfaces.srv import SetParameters
      from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
      client = self.create_client(SetParameters, '/controller_server/set_parameters')
      if client.wait_for_service(timeout_sec=1.0):
        req = SetParameters.Request()
        param = Parameter()
        param.name = 'FollowPath.max_vel_x'
        param.value = ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=speed)
        req.parameters = [param]
        client.call_async(req)
    except Exception as e:
      self.get_logger().error(f'Nav2 제어 실패: {e}')

  def stop_robot(self):
    msg = Twist()
    self.cmd_vel_pub.publish(msg)
    for _ in range(5):
      self.cmd_vel_pub.publish(msg)

  def call_clear_costmap_service(self):
    if self.clear_costmap_client.wait_for_service(timeout_sec=1.0):
      self.clear_costmap_client.call_async(ClearEntireCostmap.Request())

def main(args=None):
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
