import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap # 유령 장애물 방지
from nav_msgs.msg import Path # 경로 수신용 메시지
from std_msgs.msg import Bool
import copy # 라이다 메시지 복사용
from .inventory_db import InventoryDB
from rclpy.parameter import Parameter


class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')

    self.db = InventoryDB(base_url="http://16.184.56.119/api")
    db_wait_time = 5
    try:
      config = self.db.get_patrol_config()
      if config:
        db_wait_time = int(config.get('avoidance_wait_time', 5))
        self.get_logger().info(f"[DB] 초기 대기시간 로드 성공: {db_wait_time}초")
    except Exception as e:
      self.get_logger().error(f"[DB] 초기 데이터 로드 실패: {e}")

    self.declare_parameter('current_wait_time',db_wait_time) # UI용 장애물 대기 시간 파라미터

    current_param_val = self.get_parameter('current_wait_time').get_parameter_value().integer_value
    if current_param_val != db_wait_time:
      self.set_parameters([Parameter('current_wait_time', Parameter.Type.INTEGER, db_wait_time)])

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )

    # ---- 구독 발행----
    self.scan_sub = self.create_subscription(LaserScan, '/scan', self.scan_callback, qos_profile)
    self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
    self.plan_sub = self.create_subscription(Path, '/plan', self.plan_callback, 10) # 경로 수신
    self.teleop_sub = self.create_subscription(Twist, '/cmd_vel_teleop', self.teleop_callback, 10) # 수동

    # ---- 명령어 발행 ----
    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)
    self.virtual_obstacle_pub = self.create_publisher(LaserScan, '/scan_virtual', 10)
    self.pause_pub = self.create_publisher(Bool, '/pause_patrol', 10) # 순찰 노드에 일시정지를 요청
    self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10) # 행동트리에서 장애물 감지 여부 파악 위한 토픽

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      '/local_costmap/clear_entirely_local_costmap'
    )

    # ---- 타이머 설정 ----
    timer_pub = 0.02 # 50Hz로 상향 (정지 명령 빈도 강화)
    self.timer_second = int(1/timer_pub) # 1초당 타이머 콜백 횟수 계산
    self.timer = self.create_timer(timer_pub, self.timer_callback)

    # ---- 초기 변수 설정 ----
    # 상태 제어 및 플래그 변수
    self.is_blocked = False # 전방 길 막힘 체크
    self.is_moving_backward = False # 현재 후진 중인지 여부
    self.is_rear_blocked = False # 후방 막힘 확인 플래그
    self.is_detouring = False # 대기 후 장애물 회피(우회) 중인지 여부
    self.is_new_path_generated = False # 경로 생성 확인 플래그
    self.started_moving = False # 실제 우회 주행 시작 확인 플래그
    self.is_teleop_active = False # 수동 조작 활성화 여부
    self.is_retry_sent = False # 재출발 요청 발행 여부 체크 변수
    # UI/수동 조작 방향 감시 변수
    self.teleop_linear_x = 0.0
    self.teleop_angular_z = 0.0
    # 시간 및 카운터 변수
    self.blocked_start_time = None # 장애물 감지 시작 시각 기록용
    self.no_obstacle_start_time = None # 장애물 사라진 시각 기록용
    self.safe_distance = 0.50 # 50cm (확실한 정지 보장)
    self.current_wait_time = db_wait_time # 대기시간
    self.latest_scan_msg = None # 가짜 벽 생성 시 원본 규격을 복사하기 위한 라이다 데이터 임시 저장소
    # 현재 로봇 속도 저장
    self.current_linear_velocity = 0.0 # 현재 x축 선속도
    self.current_angular_velocity = 0.0 # 현재 z축 각속도


  def teleop_callback(self, msg):
    """
    수동조작 장애물 방지하는 함수
    """
    self.teleop_linear_x = msg.linear.x
    self.teleop_angular_z = msg.angular.z
    safe_msg = Twist()

    if abs(self.teleop_linear_x) > 0.001 or abs(self.teleop_angular_z) > 0.001:
      self.is_teleop_active = True # 수동 조작중
    else:
      self.is_teleop_active = False # 수동 조작 멈춤

    # 사용자가 긴급 정지(속도 0)를 눌렀다면 즉각 통과
    if abs(self.teleop_linear_x) < 0.001 and abs(self.teleop_angular_z) < 0.001:
      self.cmd_vel_pub.publish(msg)
      return

    if self.latest_scan_msg is None: # 라이다 데이터가 아직 안들어왔으면 수동조작 무시
      return

    # ---- 수동 전진 방어 ----
    if self.teleop_linear_x > 0.01 and self.latest_scan_msg is not None:
      front_ranges = self.latest_scan_msg.ranges[0:30] + self.latest_scan_msg.ranges[330:360]
      valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

      if valid_ranges:
        min_distance = min(valid_ranges)
        if min_distance < 0.50:
          self.get_logger().warn(f'[위험] 전방 충돌 위험! 전진을 차단합니다. 거리: {min_distance:.2f}m')
          safe_msg.linear.x = 0.0
          safe_msg.angular.z = self.teleop_angular_z
          self.cmd_vel_pub.publish(safe_msg)
          return

    # ---- 수동 후진 방어 ----
    elif self.teleop_linear_x < -0.01 :
      rear_case_1 = self.latest_scan_msg.ranges[150:210] # 60도 기준 후방
      rear_case_2 = self.latest_scan_msg.ranges[0:30] + self.latest_scan_msg.ranges[330:360] # 0도 기준 후방일 경우
      valid_rear = [r for r in (rear_case_1 + rear_case_2) if 0.1 < r < 3.0]

      if valid_rear:
        min_rear_distance = min(valid_rear)
        if min_rear_distance < 0.50:
          self.get_logger().warn(f'[위험] 후방 충돌 위험! 후진을 차단합니다. 거리: {min_rear_distance:.2f}m')
          safe_msg.linear.x = 0.0 # 후진 명령 묵살
          safe_msg.angular.z = self.teleop_angular_z # 회전은 허용
          self.cmd_vel_pub.publish(safe_msg)
          return

    # ---- 장애물이 감지되어 멈춰있는 상태에서 수동으로 피하려는 경우 ----
    if self.is_blocked:
      # 장애물 방향(전진)으로 돌진하려고 하면 -> 정지 유지
      if self.teleop_linear_x > 0.01:
        safe_msg.linear.x = 0.0
        safe_msg.angular.z = self.teleop_angular_z
        self.cmd_vel_pub.publish(safe_msg)
      # 후진이나 회전으로 빠져나가려 하면 통과
      else:
        self.cmd_vel_pub.publish(msg)
      return

    self.cmd_vel_pub.publish(msg)


  def plan_callback(self, msg):
    # 가짜 벽을 쏘는 중에만 체크 - 우회 전용
    if self.is_detouring:
      self.get_logger().info('Nav2가 새로운 우회 경로를 생성했습니다.')
      self.is_new_path_generated = True

  def odom_callback(self, msg):
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
    self.latest_scan_msg = msg

    if self.is_teleop_active: # 수동 조작 중일 때는 장애물 감지에 따른 자동 정지 방어 (수동 조작 우선)
      return

    # ---- [조건부] 후방 60도 감지 ----
    rear_ranges = msg.ranges[120:240] # 사각지대 없도록 120도 감지
    valid_rear = [r for r in rear_ranges if 0.1 < r < 3.0]

    if valid_rear and min(valid_rear) < 0.30:
      self.is_rear_blocked = True
    else:
      self.is_rear_blocked = False

    # 후진 중에 후방 장애물을 만나면 즉시 멈추고 함수 종료
    if self.is_moving_backward and self.is_rear_blocked:
      self.get_logger().warn('후방 주행 중 장애물이 감지되었습니다! 강제 정지합니다.')
      self.stop_robot()
      return

    # ---- 우회 가짜 벽을 쏘는 2초 안전 조치 ----
    if self.is_detouring or self.started_moving:
      front_ranges = msg.ranges[0:10] + msg.ranges[350:360] # 우회중 전방 20도 구역
    else:
      front_ranges = msg.ranges[0:30] + msg.ranges[330:360] # 일반 주행 중 전방 60도 구역
    valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

    status_msg = Bool()

    if len(valid_ranges) > 0:
      min_distance = min(valid_ranges)

      if min_distance < self.safe_distance: # 기본 기준거리
        if self.is_detouring or self.started_moving: # 우회중에는 멈추지 않고 건너뜀
          if min_distance >= 0.25:
            return
        if not self.is_blocked:
          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')

          self.is_blocked = True
          self.blocked_start_time = self.get_clock().now()

          status_msg = Bool()
          status_msg.data = True # 장애물 감지 상태 True
          self.obstacle_status_pub.publish(status_msg)

          pause_msg = Bool() # 순찰 노드에 일시정지 요청
          pause_msg.data = True
          self.pause_pub.publish(pause_msg)

        self.stop_robot() # 발견 유지 중일 때도 무조건 정지 명령 연속 발행
      else:
        ## ---- 장애물이 사라졌을 때 ----
        if self.is_blocked:
          if self.no_obstacle_start_time is None:
            self.no_obstacle_start_time = self.get_clock().now()

          no_obstacle = (self.get_clock().now() - self.no_obstacle_start_time).nanoseconds / 1e9

          if no_obstacle >= 1.5:
            if self.is_detouring or self.started_moving:
              return
            if self.is_blocked:
              self.get_logger().info('1.5초 동안 전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')

              pause_msg = Bool()
              pause_msg.data = False
              self.pause_pub.publish(pause_msg)

              status_msg = Bool()
              status_msg.data = False
              self.obstacle_status_pub.publish(status_msg)

              self.is_blocked = False
              self.no_obstacle_start_time = None # 다음을 위해 초기화
          else:
            self.stop_robot()

    else:
      if self.is_blocked:
        if self.no_obstacle_start_time is None:
          self.no_obstacle_start_time = self.get_clock().now()

        no_obstacle = (self.get_clock().now() - self.no_obstacle_start_time).nanoseconds / 1e9
        if no_obstacle >= 0.5:
          self.get_logger().info('전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')
          status_msg.data = False
          self.obstacle_status_pub.publish(status_msg)
          self.is_blocked = False
          self.no_obstacle_start_time = None # 다음을 위해 초기화

          retry_msg = Bool()
          retry_msg.data = True
        else:
          self.stop_robot()

  def timer_callback(self):
    if self.is_moving_backward: # 후진 중일 때는 10초 대기 및 우회 타이머 작동 X
      return

    self.current_wait_time = self.get_parameter('current_wait_time').get_parameter_value().integer_value # 대기시간 실시간 업데이트

    # ---- 장애물 대기 구간 ----
    if self.is_blocked and not self.is_teleop_active:
      self.stop_robot()

      if self.no_obstacle_start_time is not None:
        return

      elapsed_duration = self.get_clock().now() - self.blocked_start_time
      elapsed_seconds = elapsed_duration.nanoseconds / 1e9 # 나노초를 초 단위로 변환
      current_int_second = int(elapsed_seconds)

      if not hasattr(self, 'last_logged_second') or self.last_logged_second != current_int_second: # 1초 주기 로그
        if current_int_second > 0:
          self.get_logger().info(f'대기중... {current_int_second}s / {self.current_wait_time}s')
        self.last_logged_second = current_int_second

      if elapsed_seconds < self.current_wait_time:
        return
      self.get_logger().info(f'{self.current_wait_time}초가 지났습니다. 우회 판단을 요청합니다.')

      self.is_blocked = False
      self.is_detouring = True
      self.blocked_start_time = None

      if hasattr(self, 'last_logged_second'):
        del self.last_logged_second

        # 장애물 감지 상태 False로 발행 (행동트리가 우회 행동으로 넘어갈 수 있도록)
        status_msg = Bool()
        status_msg.data = False
        self.obstacle_status_pub.publish(status_msg)

    # ---- 가짜 벽 생성 및 우회 개시 구간 ----
    if self.is_detouring:
      if not self.started_moving: # 회전을 아직 시작하지 않은 최초 1회만 진입
        if self.latest_scan_msg is not None:
          fake_scan = copy.deepcopy(self.latest_scan_msg)
          fake_scan.ranges = [float('inf')] * len(fake_scan.ranges)

          # 360도 라이다 데이터 중 전방 20도 구역 설정
          num_ranges = len(fake_scan.ranges)
          idx_15 = int(num_ranges * (10 / 360))
          idx_345 = int(num_ranges * (350 / 360))

          for i in range(num_ranges):
            if i < idx_15 or i > idx_345:
              fake_scan.ranges[i] = 0.45 # 45cm에 가짜 벽 생성

          self.virtual_obstacle_pub.publish(fake_scan)

          pause_msg = Bool()
          pause_msg.data = False
          self.pause_pub.publish(pause_msg)
          self.get_logger().info('순찰 노드에 속도 잠금 해제를 요청했습니다.')

          self.started_moving = True
          self.call_clear_costmap_service() # 가짜 벽 쏘자마자 코스트맵 클리어
          self.detour_start_time = self.get_clock().now() # 우회 시작 시각 기록

      else: # 이미 우회 시작한 상태에서는 2초 동안 제자리 회전으로 장애물 피하기
        elapsed = (self.get_clock().now() - self.detour_start_time).nanoseconds / 1e9

        if elapsed < 2.0:
          twist_msg = Twist()
          twist_msg.linear.x = 0.0
          twist_msg.angular.z = 0.7 # 제자리에서 회전하여 장애물 피하기
          self.cmd_vel_pub.publish(twist_msg)
        else:
          self.is_detouring = False
          self.is_new_path_generated = False
          self.started_moving = False

          self.stop_robot()
          self.call_clear_costmap_service() # 2초 뒤에 가짜 벽 지우기
          self.get_logger().info('우회 복귀가 완료되어 장애물 감지 방어막을 다시 켭니다.')

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
