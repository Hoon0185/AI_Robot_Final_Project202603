import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap
import requests

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')
    
    # ---- [LOGIC_02 기반 통합] 웹 DB로부터 초기 설정값 수신 (LOGIC_01 Fix) ----
    default_wait_time = 10
    try:
        # 서버에서 최신 avoidance_wait_time을 가져오기 위한 HTTP GET 요청
        response = requests.get("http://16.184.56.119/api/patrol/config", timeout=2.0)
        if response.status_code == 200:
            config = response.json()
            raw_val = config.get('avoidance_wait_time', 10)
            default_wait_time = int(raw_val)
            self.get_logger().info(f'[DB] 초기 설정 수신 성공: {default_wait_time}s')
        else:
            self.get_logger().warn(f'[DB] 초기 설정 수신 실패 (HTTP {response.status_code}), 기본값 10s 사용')
    except Exception as e:
        self.get_logger().error(f'[DB] 초기 설정 서버 연결 실패: {e}, 기본값 10s 사용')

    # 파라미터 선언 및 초기값 설정 (Integer 타입 유지 필수)
    self.declare_parameter('obstacle_wait_time', default_wait_time)

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )

    # ---- 구독 설정 ----
    self.scan_sub = self.create_subscription(
      LaserScan,
      'scan',
      self.scan_callback,
      qos_profile
    )
    self.odom_sub = self.create_subscription(
      Odometry,
      'odom',
      self.odom_callback,
      10
    )

    # ---- [LOGIC_02 우선순위] 명령어 발행 토픽 (twist_mux 연동) ----
    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)

    # ---- 서비스 클라이언트 (Nav2 코스트맵 클리어용) ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      'local_costmap/clear_entirely_local_costmap'
    )

    # ---- 타이머 설정 (제어 주기 20Hz) ----
    timer_pub = 0.05 # 20Hz (기존 10Hz에서 상향)
    self.timer_second = int(1/timer_pub)
    self.timer = self.create_timer(timer_pub, self.timer_callback)
    
    # ---- [LOGIC_01 유지] 실시간 설정 동기화 타이머 (5초 주기) ----
    self.sync_timer = self.create_timer(5.0, self.sync_config_from_db)

    # ---- 초기 변수 설정 (3단계 회피 시퀀스 제어용) ----
    self.is_blocked = False
    self.clear_count = 0
    self.wait_counter = 0
    self.recovery_counter = 0     # 우회 완료 후 안정화 유예 (1초)
    self.safe_distance = 0.40     # 장애물 인식 거리 40cm
    self.min_front_dist = 9.9     # 실시간 전방 정보
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value

    # 로봇 좌표 저장용 (odom)
    self.current_x = 0.0
    self.current_y = 0.0
    self.obstacle_x = 0.0
    self.obstacle_y = 0.0

  def odom_callback(self, msg):
    self.current_x = msg.pose.pose.position.x
    self.current_y = msg.pose.pose.position.y

  def scan_callback(self, msg):
    # 전방 60도 범위의 센서 데이터 추출
    front_ranges = msg.ranges[0:30] + msg.ranges[330:360]
    valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

    # 실시간 전방 거리 최소값 업데이트
    if valid_ranges:
      self.min_front_dist = min(valid_ranges)
    else:
      self.min_front_dist = 9.9

    if valid_ranges:
      min_distance = min(valid_ranges)
      
      # 우회 시퀀스 수행 중이거나 안정화 단계에서는 센서 감지 무시
      if self.wait_counter < 0 or self.recovery_counter > 0:
        return

      # 안전 거리보다 가까운 경우 정지 및 대기 시작
      if min_distance < self.safe_distance:
        if not self.is_blocked:
          self.obstacle_x = self.current_x
          self.obstacle_y = self.current_y
          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')
          self.is_blocked = True
          self.wait_counter = 0
      else:
        # 장애물이 사라져도 설정된 시간을 다 채우기 위해 조기 재시작 로직 비활성화 유지
        pass

  def timer_callback(self):
    # 실시간 파라미터 값 로드
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value

    # 안정화 유예 시간 차감
    if self.recovery_counter > 0:
      self.recovery_counter -= 1

    max_count = int(self.wait_time_s * self.timer_second)

    # 장애물 감지 시 대기 시퀀스
    if self.is_blocked:
      self.stop_robot()
      self.wait_counter += 1

      if self.wait_counter % self.timer_second == 0 :
        seconds = self.wait_counter // self.timer_second
        self.get_logger().info(f'대기중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초 경과. 동적 우회 및 탈출 시퀀스를 시작합니다.')
        self.is_blocked = False
        # 총 4.5초 탈출 시퀀스 (회전 2.5s + 직진 1.0s + 정지 1.0s)
        self.wait_counter = -int(4.5 * self.timer_second)

    ## ---- [LOGIC_01 이식] 3단계 동적 우회 로직 ----
    elif self.wait_counter < 0:
      self.wait_counter += 1
      msg = Twist()

      # 1단계: 제자리 회전 (시야가 확보되면 즉시 직진 단계로 전환)
      if self.wait_counter < -int(2.0 * self.timer_second):
        if self.min_front_dist > 0.7:
          self.get_logger().info(f'시야 확보됨({self.min_front_dist:.2f}m). 회전을 멈추고 직진합니다.')
          self.wait_counter = -int(2.0 * self.timer_second)
          return
        msg.linear.x = 0.0
        msg.angular.z = 0.5 # 정밀 우회를 위한 저속 회전
      # 2단계: 직진 주행 (장애물 구역 이탈)
      elif self.wait_counter < -int(1.0 * self.timer_second):
        msg.linear.x = 0.15
        msg.angular.z = 0.0
      # 3단계: 정지 및 시스템 안정화 (코스트맵 클리어 병행)
      else:
        if self.wait_counter == -int(1.0 * self.timer_second) + 1:
          self.get_logger().info('탈출 완료. 시스템 안정화 및 코스트맵 초기화를 수행합니다...')
          self.call_clear_costmap()
        msg.linear.x = 0.0
        msg.angular.z = 0.0

      # twist_mux 우선순위 100번에 맞춰 발행
      self.cmd_vel_pub.publish(msg)

      if self.wait_counter == 0:
        self.stop_robot()
        self.recovery_counter = self.timer_second # 끝난 후 1초간 유예를 두어 Nav2 주도권 안전 확보
        self.get_logger().info('전체 우회 시퀀스 완료. 순찰을 재개합니다.')

  def sync_config_from_db(self):
    """주기적으로 웹 서버에서 파라미터를 가져오는 동기화 로직 (타임아웃 및 로그 최적화)"""
    try:
        # 로봇 네트워크 환경을 고려하여 타임아웃을 3.0초로 상향
        response = requests.get("http://16.184.56.119/api/patrol/config", timeout=3.0)
        if response.status_code == 200:
            config = response.json()
            raw_val = config.get('avoidance_wait_time')
            if raw_val is not None:
                new_wait_time = int(raw_val)
                if new_wait_time != self.wait_time_s:
                    import rclpy.parameter
                    new_param = rclpy.parameter.Parameter(
                        'obstacle_wait_time',
                        rclpy.parameter.Parameter.Type.INTEGER,
                        new_wait_time
                    )
                    self.set_parameters([new_param])
                    self.get_logger().info(f'[DB] 실시간 설정 업데이트: {self.wait_time_s}s -> {new_wait_time}s')
        else:
            self.get_logger().debug(f'[DB] 동기화 실패 (HTTP {response.status_code})')
    except Exception as e:
        # 터미널 도배 방지를 위해 에러 대신 경고(warn)로 출력하며 상세 내용은 생략
        self.get_logger().warn(f'[DB] 서버 통신 지연 또는 연결 불가 (확인 중...)', once=True)

  def call_clear_costmap(self):
    """Nav2 로컬 코스트맵 강제 초기화 서비스 호출"""
    if not self.clear_costmap_client.service_is_ready():
      return
    req = ClearEntireCostmap.Request()
    self.clear_costmap_client.call_async(req)
    self.get_logger().info('Local costmap 클리어 요청 전송됨.')

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
