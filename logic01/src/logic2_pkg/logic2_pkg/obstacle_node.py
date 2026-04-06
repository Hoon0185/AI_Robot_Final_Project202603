import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap
import requests
import math

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')

    # ---- [LOGIC_02 기반 통합] 웹 DB로부터 초기 설정값 수신 ----
    default_wait_time = 10
    try:
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

    self.declare_parameter('obstacle_wait_time', default_wait_time)

    qos_profile_scan = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )

    # ---- 구독 설정 ----
    self.scan_sub = self.create_subscription(
      LaserScan,
      'scan',
      self.scan_callback,
      qos_profile_scan
    )
    self.odom_sub = self.create_subscription(
      Odometry,
      'odom',
      self.odom_callback,
      10
    )

    # ---- 명령어 발행 토픽 (twist_mux 연동) ----
    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      'local_costmap/clear_entirely_local_costmap'
    )

    # ---- 타이머 설정 (제어 주기 20Hz) ----
    timer_pub = 0.05
    self.timer_second = int(1/timer_pub)
    self.timer = self.create_timer(timer_pub, self.timer_callback)
    self.sync_timer = self.create_timer(5.0, self.sync_config_from_db)

    # ---- 초기 변수 설정 ----
    self.is_blocked = False
    self.wait_counter = 0
    self.recovery_counter = 0

    # 히스테리시스 설정 (단순 거리 기반)
    self.safe_distance_enter = 0.40 # 진입
    self.safe_distance_exit = 0.55 # 해제

    self.min_front_dist = 9.9
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value

    self.current_x = 0.0
    self.current_y = 0.0

  def odom_callback(self, msg):
    self.current_x = msg.pose.pose.position.x
    self.current_y = msg.pose.pose.position.y

  def scan_callback(self, msg):
    # 전방 60도 범위의 센서 데이터 추출 (지도 필터링 제거)
    front_ranges = msg.ranges[0:31] + msg.ranges[329:361]
    valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

    # 실시간 전방 거리 최소값 업데이트
    if valid_ranges:
      self.min_front_dist = min(valid_ranges)
    else:
      self.min_front_dist = 9.9

    # 우회 시퀀스 수행 중이거나 안정화 단계에서는 센서 감지 무시
    if self.wait_counter < 0 or self.recovery_counter > 0:
      return

    # 히스테리시스 기반 정지/해제 판단
    min_dist = self.min_front_dist
    if min_dist < self.safe_distance_enter:
      if not self.is_blocked:
        self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_dist:.2f}m')
        self.is_blocked = True
        self.wait_counter = 0
    elif min_dist > self.safe_distance_exit:
      if self.is_blocked:
        # 이미 감지된 상태에서 시간을 다 채우기 전에 나가는 로직은 timer_callback에서 관리 로직 유지
        pass

  def timer_callback(self):
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value
    if self.recovery_counter > 0:
      self.recovery_counter -= 1

    max_count = int(self.wait_time_s * self.timer_second)

    if self.is_blocked:
      self.stop_robot()
      self.wait_counter += 1

      if self.wait_counter % self.timer_second == 0 :
        seconds = self.wait_counter // self.timer_second
        self.get_logger().info(f'[Blocked] 장애물 대기 중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초 경과. 동적 우회 및 탈출 시퀀스를 시작합니다.')
        self.is_blocked = False
        self.wait_counter = -int(4.5 * self.timer_second)

    elif self.wait_counter < 0:
      self.wait_counter += 1
      msg = Twist()
      if self.wait_counter < -int(2.0 * self.timer_second):
        if self.min_front_dist > 0.7:
          self.get_logger().info(f'시야 확보됨({self.min_front_dist:.2f}m). 회전을 멈추고 직진합니다.')
          self.wait_counter = -int(2.0 * self.timer_second)
          return
        msg.linear.x = 0.0
        msg.angular.z = 0.5
      elif self.wait_counter < -int(1.0 * self.timer_second):
        msg.linear.x = 0.15
        msg.angular.z = 0.0
      else:
        if self.wait_counter == -int(1.0 * self.timer_second) + 1:
          self.get_logger().info('탈출 완료. 코스트맵 초기화를 수행합니다...')
          self.call_clear_costmap()
        msg.linear.x = 0.0
        msg.angular.z = 0.0

      self.cmd_vel_pub.publish(msg)

      if self.wait_counter == 0:
        self.stop_robot()
        self.recovery_counter = self.timer_second
        self.get_logger().info('전체 우회 시퀀스 완료. 순찰을 재개합니다.')

  def sync_config_from_db(self):
    try:
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
    except Exception:
        self.get_logger().warn(f'[DB] 서버 통격 지연 (확인 중...)', once=True)

  def call_clear_costmap(self):
    if not self.clear_costmap_client.service_is_ready():
      return
    req = ClearEntireCostmap.Request()
    self.clear_costmap_client.call_async(req)

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
    pass
  finally:
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()
