import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap # 유령 장애물 방지
from nav_msgs.msg import Path # 경로 수신용 메시지
from std_msgs.msg import Bool, String
import copy # 라이다 메시지 복사용
from .inventory_db import InventoryDB

# -- nav2 서비스 통신을 위한 import --
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')
    self.db = InventoryDB(base_url="http://16.184.56.119/api")
    # self.db = InventoryDB(base_url="http://16.")

    db_wait_time = 5 # 기본값 변수
    try:
      config = self.db.get_patrol_config()
      if config:
        db_wait_time = int(config.get('avoidance_wait_time', 5))
        self.get_logger().info(f"[DB] 서버 대기시간 로드 성공: {db_wait_time}초")
      else:
        self.get_logger().warn(f"[DB] 서버 응답 없음: 기본값 {db_wait_time}초 사용")
    except Exception as e:
      self.get_logger().error(f"[DB] 서버 연결 실패: {e}")

    self.declare_parameter('current_wait_time', db_wait_time)
    self.declare_parameter('use_obstacle_avoidance', True) # 기본값 활성화

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )

    # ---- 구독 발행----
    self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile)
    self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
    self.plan_sub = self.create_subscription(Path, '/plan', self.plan_callback, 10) # 경로 수신
    self.teleop_sub = self.create_subscription(Twist, '/cmd_vel_teleop', self.teleop_callback, 10) # 수동
    self.ai_mode_sub = self.create_subscription(Bool, '/ai_mode_active', self.ai_mode_callback, 10) # AI 인식 대기 모드 활성화 여부 구독

    # ---- 명령어 발행 ----
    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)
    self.virtual_obstacle_pub = self.create_publisher(LaserScan, '/scan_virtual', 10)
    self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10) # 행동트리에서 장애물 감지 여부 파악 위한 토픽
    self.pub_ui_log = self.create_publisher(String, 'obstacle_ui_log', 10)

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(ClearEntireCostmap, '/local_costmap/clear_entirely_local_costmap')
    self.nav_param_client = self.create_client(SetParameters, '/controller_server/set_parameters')

    # ---- 타이머 설정 ----
    timer_pub = 0.02 # 50Hz로 상향 (정지 명령 빈도 강화)
    self.timer_second = int(1/timer_pub) # 1초당 타이머 콜백 횟수 계산
    self.timer = self.create_timer(timer_pub, self.timer_callback)

    # ---- 초기 변수 설정 ----
    # 상태 제어 및 플래그 변수
    self.is_blocked = False # (순찰)전방 길 막힘 체크
    self.is_moving_backward = False # 현재 후진 중인지 여부
    self.is_rear_blocked = False # 후방 막힘 확인 플래그
    self.is_teleop_active = False # 수동 조작 활성화 여부
    self.is_front_danger = False # 수동 조작 안전 플래그
    self.is_retry_sent = False # 재출발 요청 발행 여부 체크
    self.is_ai_mode = False # AI 시뮬레이션 모드 활성화 여부
    # UI/수동 조작 방향 감시 변수
    self.teleop_linear_x = 0.0
    self.teleop_angular_z = 0.0
    # 시간 및 카운터 변수
    self.blocked_start_time = None # 장애물 감지 시작 시각 기록용
    self.no_obstacle_start_time = None # 장애물 사라진 시각 기록용
    self.safe_distance = 0.30 # (확실한 정지 보장)
    self.clear_distance = self.safe_distance + 0.1 # 장애물 완전 제거 기준 (60cm)
    self.current_wait_time = db_wait_time # 대기시간
    self.latest_scan_msg = None # 최신 라이다 데이터 저장용
    self.fake_scan = None # 가짜 벽 메시지 재사용을 위한 변수

    # 현재 로봇 속도 저장
    self.current_linear_velocity = 0.0 # 현재 x축 선속도
    self.current_angular_velocity = 0.0 # 현재 z축 각속도

  def set_nav2_speed(self, max_speed):
    """Nav2의 최대 속도를 강제로 고정하거나 해제"""
    if not self.nav_param_client.wait_for_service(timeout_sec=1.0):
      self.get_logger().error('Controller Server 파라미터 서비스를 찾을 수 없습니다.')
      return

    req = SetParameters.Request()
    param = Parameter()
    param.name = 'FollowPath.max_vel_x' # FollowPath: nav2_params.yaml에 정의된 컨트롤러 이름
    param.value = ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=max_speed)

    req.parameters = [param]
    self.nav_param_client.call_async(req)
    self.get_logger().info(f'Nav2 속도 제한 설정 완료: {max_speed} m/s')

  def ai_mode_callback(self, msg):
    """AI 인식 대기 모드 활성화 여부 구독 콜백"""
    self.is_ai_mode = msg.data

  def teleop_callback(self, msg):
    """수동조작 도중 장애물 부딪힘 방지하는 함수"""
    self.teleop_linear_x = msg.linear.x
    self.teleop_angular_z = msg.angular.z
    
    # 장애물 회피 사용 여부 파라미터 실시간 체크
    use_avoidance = self.get_parameter('use_obstacle_avoidance').get_parameter_value().bool_value
    if not use_avoidance:
      self.cmd_vel_pub.publish(msg)
      return

    if abs(self.teleop_linear_x) > 0.001 or abs(self.teleop_angular_z) > 0.001:
      self.is_teleop_active = True # 수동 조작중
    else: # 사용자가 긴급 정지(속도 0)를 눌렀다면 즉각 통과
      self.is_teleop_active = False # 수동 조작 멈춤
      self.is_front_danger = False # 전방 위험 플래그 초기화
      self.cmd_vel_pub.publish(msg) # 정지 명령 바로 발행 (수동 조작 멈춤 시 즉시 정지)
      return

    if self.latest_scan_msg is None: # 라이다 데이터가 아직 안들어왔으면 수동조작 무시
      return

    final_msg = copy.deepcopy(msg) # 원본 메시지 복사
    num_ranges = len(self.latest_scan_msg.ranges)

    # ---- 수동 전진 방어 ----
    if self.teleop_linear_x > 0.0 :
      idx_30 = int(num_ranges * (15 / 360))
      idx_330 = int(num_ranges * (345 / 360))
      front_ranges = self.latest_scan_msg.ranges[0:idx_30] + self.latest_scan_msg.ranges[idx_330:num_ranges]
      valid_ranges = [r for r in front_ranges if 0.1 < r < 0.5]

      if valid_ranges and min(valid_ranges) < self.safe_distance: # 0.50m보다 가까우면 멈춤 유지
          if not self.is_front_danger:
            self.get_logger().warn(f'[수동] 전방 충돌 위험! 전진을 차단합니다. 거리: {min(valid_ranges):.2f}m')
          log_msg = String()
          log_msg.data = f'[LOGIC] 전방 충돌 위험! 수동 전진을 차단합니다. 거리: {min(valid_ranges):.2f}m'
          self.pub_ui_log.publish(log_msg)
          self.is_front_danger = True
          final_msg.linear.x = 0.0 # 속도 삭제

      elif valid_ranges and min(valid_ranges) >= self.clear_distance: # 위험 해제
        self.is_front_danger = False

    # ---- 수동 후진 방어 ----
    elif self.teleop_linear_x < 0.0 :
      idx_150 = int(num_ranges * (150 / 360))
      idx_210 = int(num_ranges * (210 / 360))
      rear_ranges = self.latest_scan_msg.ranges[idx_150:idx_210] # 60도 기준 후방
      valid_rear = [r for r in rear_ranges if 0.1 < r < 0.5]

      if valid_rear and min(valid_rear) < self.safe_distance: # 0.50m보다 가까우면 멈춤 유지
        if not self.is_front_danger:
          self.get_logger().warn(f'[수동] 후방 충돌 위험! 후진을 차단합니다. 거리: {min(valid_rear):.2f}m')
        log_msg = String()
        log_msg.data = f'[LOGIC] 후방 충돌 위험! 수동 후진을 차단합니다. 거리: {min(valid_rear):.2f}m'
        self.pub_ui_log.publish(log_msg)
        self.is_front_danger = True
        final_msg.linear.x = 0.0  # 후진 명령 묵살

    if self.is_front_danger and final_msg.linear.x > 0.0: # 위험 상태에서 전진 명령이 들어오면 차단
      final_msg.linear.x = 0.0

    self.cmd_vel_pub.publish(final_msg)


  def plan_callback(self, msg):
    """가짜 벽을 쏘는 중에만 체크 - 우회 전용"""

  def odom_callback(self, msg):
    """로봇의 이동속도 체크"""
    # ---- 현재 속도 실시간 업데이트 ----
    self.current_linear_velocity = msg.twist.twist.linear.x
    self.current_angular_velocity = msg.twist.twist.angular.z
    # ---- 로봇의 실제 이동 속도가 후진(음수)인지 체크 ----
    current_linear_velocity = msg.twist.twist.linear.x

    if current_linear_velocity < -0.01:
      self.is_moving_backward = True
    else:
      self.is_moving_backward = False


  def scan_callback(self, msg):
    """라이다 데이터 수신 시마다 장애물 감지 및 우회 로직 처리"""
    self.latest_scan_msg = msg

    if self.is_teleop_active :
      return

    # ---- [조건부] 후방 60도 감지 ----
    num_ranges = len(msg.ranges)
    idx_120 = int(num_ranges * (120 / 360))
    idx_240 = int(num_ranges * (240 / 360))

    rear_ranges = msg.ranges[idx_120:idx_240] # 사각지대 없도록 120도 감지
    valid_rear = [r for r in rear_ranges if 0.1 < r < 0.5]

    if valid_rear and min(valid_rear) < 0.30:
      self.is_rear_blocked = True
    else:
      self.is_rear_blocked = False

    # 후진 중에 후방 장애물을 만나면 즉시 멈추고 함수 종료
    if self.is_moving_backward and self.is_rear_blocked:
      self.get_logger().warn('후방 주행 중 장애물이 감지되었습니다! 강제 정지합니다.')
      self.stop_robot()
      return

    # ---- 수동 조작, AI 모드 중에는 장애물 감지 무시 ----
    if self.is_teleop_active or self.is_ai_mode :
      return

    # ---- 전방 60도 감지 ----
    num_ranges = len(msg.ranges)
    idx_10 = int(num_ranges * (10 / 360))
    idx_350 = int(num_ranges * (350 / 360))

    front_ranges = msg.ranges[0:idx_10] + msg.ranges[idx_350:num_ranges]
    valid_ranges = [r for r in front_ranges if 0.1 < r < 0.30]

    if len(valid_ranges) > 0:
      min_distance = min(valid_ranges)

      if min_distance < self.safe_distance: # 기준거리
        if not self.is_blocked: # 최초 감지
          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')

          self.is_blocked = True
          self.blocked_start_time = self.get_clock().now()
          self.no_obstacle_start_time = None

          self.set_nav2_speed(0.0) # nav2 속도를 0으로 고정

          status_msg = Bool()
          status_msg.data = True
          self.obstacle_status_pub.publish(status_msg)

        self.publish_fake_scan(msg) # 가짜 벽 연속발행
      else:
        ## ---- 장애물이 사정거리 밖으로 사라졌을 때 ----
        if self.is_blocked:
          if self.no_obstacle_start_time is None:
            self.no_obstacle_start_time = self.get_clock().now()

          no_obstacle = (self.get_clock().now() - self.no_obstacle_start_time).nanoseconds / 1e9

          if no_obstacle >= 1.5:
            self.get_logger().info('1.5초 동안 전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')
            self.call_clear_costmap_service() # 가짜 벽 제거
            self.set_nav2_speed(0.2) # 정상 속도 0.2로 복구

            self.is_blocked = False
            self.no_obstacle_start_time = None # 다음을 위해 초기화
            self.obstacle_status_pub.publish(Bool(data=False))
          else:
            self.stop_robot() # 1.5초 대기 중에는 계속 정지 유지

    else:
      # ---- 라이다에 아무 것도 안 잡힐때 ----
      if self.is_blocked:
        self.get_logger().info('전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')
        self.call_clear_costmap_service() # 1순위 지도 청소
        self.set_nav2_speed(0.2)          # 내비 속도 복구
        self.is_blocked = False
        self.no_obstacle_start_time = None
        self.obstacle_status_pub.publish(Bool(data=False))

  def timer_callback(self):
    # 후진 중일 때는 대기 및 우회 타이머 작동 X(장애물로 인해 후진중일 떄는 예외)
    if self.is_moving_backward and not self.is_blocked:
      return
    if self.is_teleop_active :
      if self.is_front_danger:
        self.stop_robot()
      return

    if self.is_ai_mode: # AI 인식 모드에서는 장애물 대기 및 우회 로직 완전 비활성화
      if self.is_blocked:
        self.get_logger().info('AI 인식 모드가 활성화되어 장애물 대기를 취소합니다.')
        self.is_blocked = False
        self.blocked_start_time = None

        status_msg = Bool()
        status_msg.data = False
        self.obstacle_status_pub.publish(status_msg)
      return

    self.current_wait_time = self.get_parameter('current_wait_time').get_parameter_value().integer_value # 대기시간 실시간 업데이트

    # ---- 장애물 대기 구간 ----
    if self.is_blocked:
      elapsed_duration = self.get_clock().now() - self.blocked_start_time
      elapsed_seconds = elapsed_duration.nanoseconds / 1e9 # 나노초를 초 단위로 변환

      back_off_start_time = self.current_wait_time - 2.0 # 후진 타이밍 (대기시간 종료 2초 전 시작)
      stay_start = self.current_wait_time - 1.3 # 후진 종료 및 최종 정지 시작 (종료 1.3초 전)

      if elapsed_seconds < back_off_start_time:
        # 1단계: 정지대기
        self.stop_robot()
      elif back_off_start_time <= elapsed_seconds < stay_start:
        # 2단계: 대기 종료 직전 후진해서 공간 확보 (2.0 - 1.3 = 0.7초)
        msg = Twist()
        msg.linear.x = -0.07  # 아주 느리게 후진
        self.cmd_vel_pub.publish(msg)
        if int(elapsed_seconds * 10) % 5 == 0:
          self.get_logger().info('공간 확보를 위해 살짝 후진합니다...')
      elif stay_start <= elapsed_seconds < self.current_wait_time:
        # 3단계: 1.3초간 최종 정지 및 Nav2 경로 계산 대기
        self.stop_robot()
        if int(elapsed_seconds * 10) % 5 == 0:
          self.get_logger().info('후진 완료. Nav2 우회 준비 중...')
      elif elapsed_seconds >= self.current_wait_time:
        # 4단계: 해제 및 주행 재개
        self.get_logger().info(f'{self.current_wait_time}초 경과. 자물쇠를 풀고 Nav2 회피를 허용합니다.')
        self.set_nav2_speed(0.2)
        self.is_blocked = False
        self.blocked_start_time = None

        # Nav2 비헤이비어 트리에 장애물이 없다고 알려서 회피 기동을 시작하게 함
        self.obstacle_status_pub.publish(Bool(data=False))


  def call_clear_costmap_service(self):
    if not self.clear_costmap_client.wait_for_service(timeout_sec=1.0):
      self.get_logger().error('코스트맵 클리어 서비스를 찾을 수 없습니다.')
      return

    request = ClearEntireCostmap.Request()
    future = self.clear_costmap_client.call_async(request)


  def stop_robot(self):
    msg = Twist()
    msg.linear.x = 0.0
    msg.angular.z = 0.0
    self.cmd_vel_pub.publish(msg)
    # 즉각적인 우선순위 점유를 위해 연속 발행
    for _ in range(5):
      self.cmd_vel_pub.publish(msg)

def main(args=None):
  if not rclpy.ok():
    rclpy.init(args=args)
  node = ObstacleNode()
  try:
    rclpy.spin(node)
  except KeyboardInterrupt:
    node.get_logger().info('Keyboard interrupt')
  finally:
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()
