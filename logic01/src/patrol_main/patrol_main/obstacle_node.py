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

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')

    self.db = InventoryDB(base_url="http://16.184.56.119:8000")
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

    self.declare_parameter('current_wait_time',db_wait_time) # UI용 장애물 대기 시간 파라미터

    self.get_parameter('current_wait_time').get_parameter_value().integer_value

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
    self.pause_pub = self.create_publisher(Bool, '/pause_patrol', 10) # 순찰 노드에 일시정지를 요청
    self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10) # 행동트리에서 장애물 감지 여부 파악 위한 토픽
    self.pub_ui_log = self.create_publisher(String, 'obstacle_ui_log', 10)

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
    self.is_blocked = False # (순찰)전방 길 막힘 체크
    self.is_moving_backward = False # 현재 후진 중인지 여부
    self.is_rear_blocked = False # 후방 막힘 확인 플래그
    self.is_detouring = False # 대기 후 장애물 회피(우회) 중인지 여부
    self.is_new_path_generated = False # 경로 생성 확인 플래그
    self.is_started_moving = False # 실제 우회 주행 시작 확인 플래그
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
    self.safe_distance = 0.50 # 50cm (확실한 정지 보장)
    self.clear_distance = self.safe_distance + 0.1 # 장애물 완전 제거 기준 (60cm)
    self.current_wait_time = db_wait_time # 대기시간
    self.latest_scan_msg = None # 최신 라이다 데이터 저장용
    self.fake_scan = None # 가짜 벽 메시지 재사용을 위한 변수
    self.detour_direction = 0.7 # 우회 회전 방향 (양수: 좌회전, 음수: 우회전)
    # 현재 로봇 속도 저장
    self.current_linear_velocity = 0.0 # 현재 x축 선속도
    self.current_angular_velocity = 0.0 # 현재 z축 각속도


  def ai_mode_callback(self, msg):
    """AI 인식 대기 모드 활성화 여부 구독 콜백"""
    self.is_ai_mode = msg.data

  def teleop_callback(self, msg):
    """수동조작 도중 장애물 부딪힘 방지하는 함수"""
    self.teleop_linear_x = msg.linear.x
    self.teleop_angular_z = msg.angular.z

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
      idx_30 = int(num_ranges * (30 / 360))
      idx_330 = int(num_ranges * (330 / 360))
      front_ranges = self.latest_scan_msg.ranges[0:idx_30] + self.latest_scan_msg.ranges[idx_330:num_ranges]
      valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

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
      valid_rear = [r for r in rear_ranges if 0.1 < r < 3.0]

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
    """라이다 데이터 수신 시마다 장애물 감지 및 우회 로직 처리"""
    self.latest_scan_msg = msg

    if self.is_teleop_active or self.is_detouring :
      return

    # ---- [조건부] 후방 60도 감지 ----
    num_ranges = len(msg.ranges)
    idx_120 = int(num_ranges * (120 / 360))
    idx_240 = int(num_ranges * (240 / 360))

    rear_ranges = msg.ranges[idx_120:idx_240] # 사각지대 없도록 120도 감지
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

    # ---- 수동 조작, AI 모드, 우회 중에는 장애물 감지 무시 ----
    if self.is_teleop_active or self.is_ai_mode or self.is_detouring or self.is_started_moving:
      return

    # ---- 전방 60도 감지 ----
    num_ranges = len(msg.ranges)
    idx_30 = int(num_ranges * (30 / 360))
    idx_330 = int(num_ranges * (330 / 360))

    front_ranges = msg.ranges[0:idx_30] + msg.ranges[idx_330:num_ranges]
    valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

    if len(valid_ranges) > 0:
      min_distance = min(valid_ranges)

      if min_distance < self.safe_distance: # 기준거리
        if not self.is_blocked:
          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')

          self.is_blocked = True
          self.blocked_start_time = self.get_clock().now()
          self.no_obstacle_start_time = None

          status_msg = Bool() # 행동트리에 장애물 감지 상태 발행
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
        self.get_logger().info('전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')
        self.is_blocked = False
        self.no_obstacle_start_time = None # 다음을 위해 초기화

        status_msg = Bool()
        status_msg.data = False
        self.obstacle_status_pub.publish(status_msg)

        pause_msg = Bool()
        pause_msg.data = False
        self.pause_pub.publish(pause_msg)

  def timer_callback(self):
    if self.is_moving_backward: # 후진 중일 때는 10초 대기 및 우회 타이머 작동 X
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

      if elapsed_seconds >= self.current_wait_time:
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
    elif self.is_detouring:
      if not self.is_started_moving: # 회전을 아직 시작하지 않은 최초 1회만 진입
        if self.latest_scan_msg is not None:
          num_ranges = len(self.latest_scan_msg.ranges)

          # 인덱스 범위 지정 (라이다 데이터의 배열 길이에 맞춰 동적 계산)
          left_idx_start = int(num_ranges * (30 / 360))
          left_idx_end = int(num_ranges * (60 / 360))
          right_idx_start = int(num_ranges * (300 / 360))
          right_idx_end = int(num_ranges * (330 / 360))

          left_distances = [r for r in self.latest_scan_msg.ranges[left_idx_start:left_idx_end] if 0.1 < r < 3.0]
          right_distances = [r for r in self.latest_scan_msg.ranges[right_idx_start:right_idx_end] if 0.1 < r < 3.0]

          left_avg = sum(left_distances) / len(left_distances) if left_distances else 0.0
          right_avg = sum(right_distances) / len(right_distances) if right_distances else 0.0

          if left_avg >= right_avg:
            self.detour_direction = 0.7 # 좌회전 (양수)
            self.get_logger().info('라이다 분석 결과: 좌측 공간이 넓어 좌회전으로 우회합니다.')
          else:
            self.detour_direction = -0.7 # 우회전 (음수)
            self.get_logger().info('라이다 분석 결과: 우측 공간이 넓어 우회전으로 우회합니다.')

          # 가짜벽 생성
          self.fake_scan = copy.deepcopy(self.latest_scan_msg)
          self.fake_scan.ranges = [float('inf')] * len(self.fake_scan.ranges)

          # 360도 라이다 데이터 중 전방 40도 구역 설정
          num_ranges = len(self.fake_scan.ranges)
          idx_15 = int(num_ranges * (20 / 360))
          idx_345 = int(num_ranges * (340 / 360))

          for i in range(num_ranges):
            if i < idx_15 or i > idx_345:
              self.fake_scan.ranges[i] = 0.6 # 60cm에 가짜 벽 생성

          self.virtual_obstacle_pub.publish(self.fake_scan)

          pause_msg = Bool()
          pause_msg.data = False
          self.pause_pub.publish(pause_msg)
          self.get_logger().info('순찰 노드에 속도 잠금 해제를 요청했습니다.')

          self.is_started_moving = True
          self.call_clear_costmap_service() # 가짜 벽 쏘자마자 코스트맵 클리어
          self.detour_start_time = self.get_clock().now() # 우회 시작 시각 기록

      else: # 이미 우회 시작한 상태에서는 5초 동안 제자리 회전으로 장애물 피하기
        elapsed = (self.get_clock().now() - self.detour_start_time).nanoseconds / 1e9

        if elapsed < 0.5:
          # [추가] 우회 중 정면에 장애물이 사라졌는지 체크 (조기 종료 로직)
          if self.latest_scan_msg is not None:
            num_ranges = len(self.latest_scan_msg.ranges)
            idx_15 = int(num_ranges * (15 / 360))
            idx_345 = int(num_ranges * (345 / 360))
            front_area = self.latest_scan_msg.ranges[0:idx_15] + self.latest_scan_msg.ranges[idx_345:num_ranges]
            valid_front = [r for r in front_area if 0.1 < r < 3.0]

            # 정면 1.0m 이내에 아무것도 없으면 조기 종료 (최소 1초는 회전 후 판단)
            if elapsed > 1.0 and (not valid_front or min(valid_front) > 1.0):
              self.get_logger().info('우회 중 정면 경로가 확보되어 조기에 회전을 멈추고 주행을 재개합니다.')
              self.is_detouring = False
              self.is_started_moving = False
              self.fake_scan = None
              self.stop_robot()
              self.call_clear_costmap_service()
              return

          twist_msg = Twist()
          twist_msg.linear.x = 0.0
          twist_msg.angular.z = self.detour_direction # 분석한 방향으로 회전
          self.cmd_vel_pub.publish(twist_msg)

          if self.fake_scan is not None: # 우회 시작 후에도 가짜 벽 유지 (실제 장애물과의 충돌 방지)
            self.virtual_obstacle_pub.publish(self.fake_scan) # 교체 발행으로 가짜 벽 지속
        else:
          self.is_detouring = False
          self.is_new_path_generated = False
          self.is_started_moving = False
          self.fake_scan = None # 가짜 벽 메시지 초기화

          self.stop_robot()
          self.call_clear_costmap_service() # 3초 뒤에 가짜 벽 지우기
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
