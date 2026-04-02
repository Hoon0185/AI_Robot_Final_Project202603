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
    
    # ---- 웹 DB에서 초기 설정값 가져오기 ----
    default_wait_time = 10
    try:
        response = requests.get("http://16.184.56.119/api/patrol/config", timeout=2.0)
        if response.status_code == 200:
            config = response.json()
            default_wait_time = int(config.get('avoidance_wait_time', 10))
            self.get_logger().info(f'[DB] 초기 설정 수신 성공: {default_wait_time}s')
        else:
            self.get_logger().warn(f'[DB] 초기 설정 수신 실패 (HTTP {response.status_code})')
    except Exception as e:
        self.get_logger().error(f'[DB] 초기 설정 서버 연결 실패: {e}')

    self.declare_parameter('obstacle_wait_time', default_wait_time)

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )
    # ---- 구독 ----
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
    # ---- 명령어 발행 ----
    # self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10) # 기존
    self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel_obstacle', 10)

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      'local_costmap/clear_entirely_local_costmap'
    )

    # ---- 타이머 설정 ----
    timer_pub = 0.1 # 10Hz로 최적화
    self.timer_second = int(1/timer_pub) # 1초당 타이머 콜백 횟수 계산
    self.timer = self.create_timer(timer_pub, self.timer_callback)
    
    # ---- 웹 설정 주기적 동기화 타이머 (5초) ----
    self.sync_timer = self.create_timer(5.0, self.sync_config_from_db)

    # ---- 초기 변수 설정 ----
    self.is_blocked = False # 길 막힘 체크
    self.clear_count = 0 # 장애물이 확실히 사라졌는지 체크
    self.wait_counter = 0 # 대기시간 측정
    self.recovery_counter = 0 # 우회 완료 후 안정화 유예 시간
    self.safe_distance = 0.40 # 40cm로 상향
    self.min_front_dist = 9.9 # 실시간 전방 최소 거리 초기값
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value # 대기시간

    # ---- 현재 로봇 좌표 저장 ----
    self.current_x = 0.0
    self.current_y = 0.0
    self.obstacle_x = 0.0
    self.obstacle_y = 0.0

  def odom_callback(self, msg): # 현재 좌표 실시간 업데이트
    self.current_x = msg.pose.pose.position.x
    self.current_y = msg.pose.pose.position.y

  def scan_callback(self, msg):
    front_ranges = msg.ranges[0:30] + msg.ranges[330:360] # 60도
    valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0] # 유효반경 ~ 3m

    if valid_ranges:
      self.min_front_dist = min(valid_ranges) # 실시간 거리 정보 업데이트
    else:
      self.min_front_dist = 9.9 # 전방 장애물 없음

    if valid_ranges:
      min_distance = min(valid_ranges)

      # 우회 시퀀스 진행 중이거나 안정화 유예 기간(1초) 중에는 장애물 감지 무시
      if self.wait_counter < 0 or self.recovery_counter > 0:
        return
      else:
        check_dist = self.safe_distance # 기본 장애물 기준 거리

      if min_distance < check_dist:
        self.clear_count = 0 # 장애물 감지 -> clear_count 초기화
        if not self.is_blocked:
          ## ---- 장애물 좌표 기록 ----
          self.obstacle_x = self.current_x
          self.obstacle_y = self.current_y

          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')
          self.is_blocked = True
          self.wait_counter = 0
        # self.stop_robot() # 타이머 콜백에서 처리하도록 위임하여 중복 발행 방지
      else:
        ## ---- 장애물이 사라졌을 때 (10초 강제 대기를 위해 조기 취소 로직 비활성화) ----
        if self.is_blocked and self.wait_counter >= 0:
          pass # 기존의 0.5초만에 재출발 해버리는 로직을 무효화하여 무조건 10초 대기 타이머를 타게 함.

  def timer_callback(self):
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value # 대기시간 업데이트

    if self.recovery_counter > 0:
      self.recovery_counter -= 1

    max_count = int(self.wait_time_s * self.timer_second)

    if self.is_blocked:
      self.stop_robot()
      self.wait_counter += 1

      if self.wait_counter % self.timer_second == 0 : # 1초 주기 로그
        seconds = self.wait_counter // self.timer_second
        self.get_logger().info(f'대기중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초 경과. 우회 및 탈출 시퀀스를 시작합니다.')
        self.is_blocked = False
        # 총 4.5초 탈출 시퀀스 (회전 2s + 직진 1.5s + 정지 1s)
        self.wait_counter = -int(4.5 * self.timer_second)

    ## ---- 우회 로직 (동적 센서 기반) ----
    elif self.wait_counter < 0:
      self.wait_counter += 1
      msg = Twist()

      # 1. 0.0 ~ 2.0초: 제자리 회전 (시야 확보 시 중단)
      if self.wait_counter < -int(2.5 * self.timer_second):
        if self.min_front_dist > 0.7:
          self.get_logger().info(f'시야 확보됨({self.min_front_dist:.2f}m). 회전을 멈추고 직진합니다.')
          self.wait_counter = -int(2.5 * self.timer_second) # 직진 단계로 점프
          return
        
        msg.linear.x = 0.0
        msg.angular.z = 0.5 # 정밀도를 위한 저속 회전
      # 2. 2.0 ~ 3.5초: 직진 탈출
      elif self.wait_counter < -int(1.0 * self.timer_second):
        msg.linear.x = 0.15 
        msg.angular.z = 0.0
      # 3. 3.5 ~ 4.5초: 정지 및 코스트맵 클리어
      else:
        if self.wait_counter == -int(1.0 * self.timer_second) + 1:
          self.get_logger().info('직진 완료. 정지 후 시스템을 안정화합니다...')
          self.call_clear_costmap()

        msg.linear.x = 0.0
        msg.angular.z = 0.0

      self.cmd_vel_pub.publish(msg)

      if self.wait_counter == 0:
        self.stop_robot()
        self.recovery_counter = self.timer_second # 완료 후 1초간 유예
        self.get_logger().info('우회 시퀀스 완료. 순찰을 재개합니다.')

  def sync_config_from_db(self):
    """주기적으로 웹 서버에서 최신 설정값을 가져와 동기화 (디버깅 강화 버전)"""
    try:
        response = requests.get("http://16.184.56.119/api/patrol/config", timeout=1.5)
        
        if response.status_code == 200:
            config = response.json()
            new_wait_time = int(config.get('avoidance_wait_time', 10))
            
            if new_wait_time != self.wait_time_s:
                # rclpy 방식을 사용하여 파라미터 업데이트 (Type 2: INTEGER)
                import rclpy.parameter
                new_param = rclpy.parameter.Parameter(
                    'obstacle_wait_time',
                    rclpy.parameter.Parameter.Type.INTEGER,
                    new_wait_time
                )
                self.set_parameters([new_param])
                self.get_logger().info(f'[DB] 회피 대기시간 동기화 완료: {self.wait_time_s}s -> {new_wait_time}s')
        else:
            self.get_logger().warn(f'[DB] 주기적 동기화 실패: HTTP {response.status_code}')

    except requests.exceptions.Timeout:
        self.get_logger().error('[DB] 서버 연결 타임아웃 (1.5s)')
    except requests.exceptions.ConnectionError:
        self.get_logger().error('[DB] 서버 연결 불가 (네트워크 확인 필요)')
    except Exception as e:
        self.get_logger().error(f'[DB] 동기화 중 에러 발생: {e}')

  def call_clear_costmap(self):
    """Nav2 로컬 코스트맵 초기화"""
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
