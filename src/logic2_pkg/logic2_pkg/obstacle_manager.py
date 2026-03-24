import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

class ObstacleManager(Node):
  def __init__(self):
    super().__init__('obstacle_manager')

    # ---- 라이다(센서) 구독 ----
    self.scan_sub = self.create_subscription(
      LaserScan,
      'scan',
      self.scan_callback,
      10
      )
    # ---- 로봇 실시간 위치 구독 ----
    self.odom_sub = self.create_subscription(
      Odometry,
      'odom',
      self.odom_callback,
      10
    )
    # ---- 구동 신호 전송 ----
    self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 10)

    # ---- 타이머 설정(0.1초 기준) ----
    self.timer = self.create_timer(0.1, self.timer_callback)

    # ---- 초기 변수 설정 ----
    self.is_blocked = False # 길 막힘 체크
    self.wait_counter = 0 # 대기시간 측정
    self.safe_distance = 0.5 # 50cm 기준

    # ---- 현재 로봇 좌표 저장 ----
    self.current_x = 0.0
    self.current_y = 0.0
    self.obstacle_x = 0.0
    self.obstacle_y = 0.0

  def odom_callback(self, msg): # 현재 좌표 실시간 업데이트
    self.current_x = msg.pose.pose.position.x
    self.current_y = msg.pose.pose.position.y

  def scan_callback(self, msg):
    front_ranges = msg.ranges[0:5] + msg.ranges[355:360] # 10도
    valid_ranges = [r for r in front_ranges if r > 0.0]

    if valid_ranges:
      min_distance = min(valid_ranges)

      if min_distance < self.safe_distance:
        if not self.is_blocked:
          ## ---- 장애물 좌표 기록 ----
          self.obstacle_x = self.current_x
          self.obstacle_y = self.current_y

          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')
          self.is_blocked = True
          self.stop_robot() # 발견 -> 정지
        else:
          ## ---- 장애물이 사라졌을 때(수정 예정) ----
          pass

  def timer_callback(self):
    if self.is_blocked:
      self.stop_robot()

      self.wait_counter += 1

      if self.wait_counter % 10 == 0 : # 1초 주기 로그
        seconds = self.wait_counter // 10
        self.get_logger().info(f'로딩중... {seconds}s / 10s')

      if self.wait_counter >= 100:
        self.get_logger().info('10초가 지났습니다. 경로를 재탐색합니다.')
        self.is_blocked = False
        self.wait_counter = 0
        ## ---- 우회 로직(수정 예정) ----

  def stop_robot(self):
    msg = Twist()
    msg.linear.x = 0.0
    msg.angular.z = 0.0
    self.cmd_vel_pub.publish(msg)

def main(args=None):
  rclpy.init(args=args)
  node = ObstacleManager()
  try:
    rclpy.spin(node)
  except KeyboardInterrupt:
    node.get_logger().info('Keyboard interrupt')
  finally:
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()
