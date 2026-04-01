import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap

class ObstacleNode(Node):
  def __init__(self):
    super().__init__('patrol_obstacle_node')
    self.declare_parameter('obstacle_wait_time',10) # 장애물 대기 시간(ui 조정을 위함)

    qos_profile = QoSProfile(
      reliability=ReliabilityPolicy.BEST_EFFORT,
      depth=10
    )
    # ---- 구독 ----
    self.scan_sub = self.create_subscription(
      LaserScan,
      '/scan',
      self.scan_callback,
      qos_profile
    )
    self.odom_sub = self.create_subscription(
      Odometry,
      '/odom',
      self.odom_callback,
      10
    )
    # ---- 명령어 발행 ----
    # self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10) # 기존
    self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_obstacle', 10)
    self.get_logger().info('Obstacle Node initialized with absolute topic /cmd_vel_obstacle')

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      'local_costmap/clear_entirely_local_costmap'
    )

    # ---- 타이머 설정 ----
    timer_pub = 0.02 # 50Hz로 상향 (정지 명령 빈도 강화)
    self.timer_second = int(1/timer_pub) # 1초당 타이머 콜백 횟수 계산
    self.timer = self.create_timer(timer_pub, self.timer_callback)

    # ---- 초기 변수 설정 ----
    self.is_blocked = False # 길 막힘 체크
    self.clear_count = 0 # 장애물이 확실히 사라졌는지 체크
    self.wait_counter = 0 # 대기시간 측정
    self.safe_distance = 0.40 # 40cm로 살짝 상향 (확실한 정지 보장)
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
      min_distance = min(valid_ranges)

      if self.wait_counter < 0:
        # check_dist = 0.20 # 우회 중 장애물 기준 거리 (20cm)
        return # 우회 중에는 장애물 감지 무시(수정예정)
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
        self.stop_robot() # 발견 유지 중일 때도 무조건 정지 명령 연속 발행
      else:
        ## ---- 장애물이 사라졌을 때 (10초 강제 대기를 위해 조기 취소 로직 비활성화) ----
        if self.is_blocked and self.wait_counter >= 0:
          pass # 기존의 0.5초만에 재출발 해버리는 로직을 무효화하여 무조건 10초 대기 타이머를 타게 함.

  def timer_callback(self):
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value # 대기시간 실시간 업데이트
    max_count = int(self.wait_time_s * self.timer_second) # 1초

    if self.is_blocked:
      self.stop_robot()
      self.wait_counter += 1

      if self.wait_counter % self.timer_second == 0 : # 1초 주기 로그
        seconds = self.wait_counter // self.timer_second
        self.get_logger().info(f'대기중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초가 지났습니다. 우회 회전을 시작합니다.')
        self.is_blocked = False
        self.wait_counter = -int(2 * self.timer_second) # 우회 로직 진입 (2초)

    ## ---- 우회 로직(수정 예정) ----
    elif self.wait_counter < 0:
      self.wait_counter += 1

      msg = Twist()
      msg.linear.x = 0.0
      msg.angular.z = 1.0
      self.cmd_vel_pub.publish(msg)

      if self.wait_counter == 0:
        self.get_logger().info('우회 회전 완료. 순찰을 재개합니다.')

  def stop_robot(self):
    msg = Twist()
    msg.linear.x = 0.0
    msg.angular.z = 0.0
    self.cmd_vel_pub.publish(msg)

def main(args=None):
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
