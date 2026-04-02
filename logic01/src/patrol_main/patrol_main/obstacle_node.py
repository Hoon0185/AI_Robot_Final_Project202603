import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from nav2_msgs.srv import ClearEntireCostmap # 유령 장애물 방지
from nav_msgs.msg import Path # 경로 수신용 메시지
from std_msgs.msg import Bool
import math # inf 및 nan 처리
import copy # 라이다 메시지 복사용

# ---- 라이프사이클 서비스 규격 추가 ----
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition


class ObstacleNode(Node):
  def __init__(self):
    super().__init__('obstacle_node')
    self.declare_parameter('obstacle_wait_time',10) # UI용 장애물 대기 시간 파라미터

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
    self.emergency_pub = self.create_publisher(Bool, '/emergency_stop', 10)
    self.virtual_obstacle_pub = self.create_publisher(LaserScan, '/scan_virtual', 10)
    # 행동트리에서 장애물 감지 여부 파악 위한 토픽
    self.obstacle_status_pub = self.create_publisher(Bool, '/obstacle_detected_status', 10)

    # ---- 서비스 클라이언트 ----
    self.clear_costmap_client = self.create_client(
      ClearEntireCostmap,
      '/local_costmap/clear_entirely_local_costmap'
    )
    self.change_state_client = self.create_client( # Nav2 컨트롤러 서버 라이프사이클 클라이언트 추가
      ChangeState,
      '/controller_server/change_state'
    )

    # ---- 타이머 설정 ----
    timer_pub = 0.02 # 50Hz로 상향 (정지 명령 빈도 강화)
    self.timer_second = int(1/timer_pub) # 1초당 타이머 콜백 횟수 계산
    self.timer = self.create_timer(timer_pub, self.timer_callback)

    # ---- 초기 변수 설정 ----
    # 상태 제어 및 플래그 변수
    self.is_blocked = False # 전방 길 막힘 체크
    self.is_moving_backward = False # 현재 후진 중인지 여부
    self.is_detouring = False # 대기 후 장애물 회피(우회) 중인지 여부
    self.is_new_path_generated = False # 경로 생성 확인 플래그
    self.started_moving = False # 실제 우회 주행 시작 확인 플래그
    self.is_teleop_active = False # 수동 조작 활성화 여부
    self.is_nav_paused = False # Nav2 주행 일시정지 여부
    # UI/수동 조작 방향 감시 변수
    self.teleop_linear_x = 0.0
    self.teleop_angular_z = 0.0
    # 시간 및 카운터 변수
    self.wait_counter = 0 # 대기시간 측정
    self.safe_distance = 0.40 # 40cm로 살짝 상향 (확실한 정지 보장)
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value # 대기시간
    self.latest_scan_msg = None # 가짜 벽 생성 시 원본 규격을 복사하기 위한 라이다 데이터 임시 저장소
    # 현재 로봇 속도 저장
    self.current_linear_velocity = 0.0 # 현재 x축 선속도
    self.current_angular_velocity = 0.0 # 현재 z축 각속도


  def teleop_callback(self, msg):
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

    # 장애물이 감지되어 멈춰있는 상태일 때
    if self.is_blocked:
      # 장애물 방향(전진)으로 돌진하려고 하면 -> 전진 속도만 0.0으로 정지 유지
      if self.teleop_linear_x > 0.01:
        safe_msg.linear.x = 0.0
        safe_msg.angular.z = self.teleop_angular_z # 회전은 허용
        self.cmd_vel_pub.publish(safe_msg)
      # 후진이나 회전으로 빠져나가려 하면 통과
      else:
        self.cmd_vel_pub.publish(msg)

    # 평소에 장애물이 없을 때 UI 조작 그대로 통과
    else:
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
    processed_ranges = msg.ranges # inf 및 nan 처리

    # ---- [조건부] 후방 60도 감지 ----
    if self.is_moving_backward:
      rear_ranges = msg.ranges[150:210]
      valid_rear = [r for r in rear_ranges if 0.1 < r < 3.0]

      if valid_rear:
        min_rear_distance = min(valid_rear)
        if min_rear_distance < 0.30:
          self.get_logger().warn(f'후방 장애물이 감지되었습니다! 거리: {min_rear_distance:.2f}m')
          self.stop_robot()

          msg_stop = Bool()
          msg_stop.data = True
          self.emergency_pub.publish(msg_stop)
          self.obstacle_status_pub.publish(msg_stop)

          self.is_blocked = True
          return

        if self.is_blocked: # 후방 장애물이 사라졌다면 즉시 해제
          self.get_logger().info('후방 장애물이 사라졌습니다. 주행을 재개합니다.')
          self.is_blocked = False
          self.wait_counter = 0 # 다음 장애물을 위해 카운트 0으로 리셋

          status_msg = Bool()
          status_msg.data = False
          self.obstacle_status_pub.publish(status_msg)
          return
      self.is_blocked = False
      return # 후진 중에는 전방 장애물 인식 X

    # ---- 우회 가짜 벽을 쏘는 2초 안전 조치 ----
    if self.is_detouring:
      front_ranges = processed_ranges[0:30] + processed_ranges[330:360]
      valid_ranges = [r for r in front_ranges if 0.1 <= r < 3.0]
    else:
      front_ranges = processed_ranges[0:30] + processed_ranges[330:360]
      valid_ranges = [r for r in front_ranges if 0.1 < r < 3.0]

    status_msg = Bool()

    if len(valid_ranges) > 0:
      min_distance = min(valid_ranges)
      check_dist = self.safe_distance # 기본 장애물 기준 거리

      if min_distance < check_dist:
        if not self.is_blocked:
          self.get_logger().warn(f'장애물이 감지되었습니다! 거리: {min_distance:.2f}m')

          self.is_blocked = True
          self.wait_counter = 0

          status_msg.data = True # 장애물 감지 상태 True
          self.obstacle_status_pub.publish(status_msg)
          self.pause_navigation() # Nav2 주행을 일시 정지

        self.stop_robot() # 발견 유지 중일 때도 무조건 정지 명령 연속 발행
      else:
        ## ---- 장애물이 사라졌을 때 ----
        if self.is_blocked:
          status_msg.data = False
          self.wait_counter = 0 # 다음 장애물 감지를 위해 카운터 초기화
          self.obstacle_status_pub.publish(status_msg)
          self.is_blocked = False

          self.resume_navigation() # Nav2 주행 재개
    else:
      if self.is_blocked:
        self.get_logger().info('전방에 장애물이 완전히 사라졌습니다. 주행을 재개합니다.')
        status_msg.data = False
        self.wait_counter = 0
        self.obstacle_status_pub.publish(status_msg)
        self.is_blocked = False

        self.resume_navigation() # Nav2 주행 재개

  def timer_callback(self):
    if self.is_moving_backward: # 후진 중일 때는 10초 대기 및 우회 타이머 작동 X
      return

    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value # 대기시간 실시간 업데이트
    max_count = int(self.wait_time_s * self.timer_second) # 1초

    if self.is_blocked:
      self.wait_counter += 1

      if self.wait_counter % self.timer_second == 0: # 1초 주기 로그
        seconds = self.wait_counter // self.timer_second
        self.get_logger().info(f'대기중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초가 지났습니다. 우회 판단을 요청합니다.')

        self.is_blocked = False
        self.wait_counter = 0
        self.is_detouring = True

        self.resume_navigation() # Nav2 주행 재개

        # 장애물 감지 상태 False로 발행 (행동트리가 우회 행동으로 넘어갈 수 있도록)
        status_msg = Bool()
        status_msg.data = False
        self.obstacle_status_pub.publish(status_msg)

    if self.is_detouring:
      # 새 경로가 안 짜였거나, 짜였어도 정지 상태면 계속 가짜 벽 발행
      if not (self.is_new_path_generated and self.started_moving):
        if self.latest_scan_msg is not None:
          fake_scan = copy.deepcopy(self.latest_scan_msg)
          fake_scan.ranges = [float('inf')] * len(fake_scan.ranges)

          for i in range(len(fake_scan.ranges)):
            if i < 15 or i > 345:
              fake_scan.ranges[i] = 0.2

          self.virtual_obstacle_pub.publish(fake_scan)

      # 경로가 짜인 상태에서 로봇이 움직이기 시작했는지 체크 (속도 기준 0.05)
      if self.is_new_path_generated and not self.started_moving:
        if abs(self.current_linear_velocity) > 0.05 or abs(self.current_angular_velocity) > 0.05:
          self.started_moving = True
          self.get_logger().info('로봇이 우회 이동을 시작했습니다. 가짜 벽을 해제합니다.')

          self.call_clear_costmap_service()

          # 다음 장애물 상황을 위해 상태 초기화
          self.is_detouring = False
          self.is_new_path_generated = False
          self.started_moving = False

  def call_clear_costmap_service(self):
    if not self.clear_costmap_client.wait_for_service(timeout_sec=1.0):
      self.get_logger().error('코스트맵 클리어 서비스를 찾을 수 없습니다.')
      return

    request = ClearEntireCostmap.Request()
    future = self.clear_costmap_client.call_async(request)


  def pause_navigation(self):
    """# Nav2 컨트롤러 서버 정지 함수"""
    if not self.is_nav_paused:
      if not self.change_state_client.wait_for_service(timeout_sec=1.0):
        self.get_logger().error('Nav2 상태 제어 서비스를 찾을 수 없습니다.')
        return

      request = ChangeState.Request()
      request.transition.id = Transition.TRANSITION_DEACTIVATE # 노드 정지 신호
      self.change_state_client.call_async(request)
      self.get_logger().info('Nav2 주행을 일시정지(Pause) 하였습니다.')
      self.is_nav_paused = True


  def resume_navigation(self):
    """Nav2 컨트롤러 서버 주행 재개 함수"""
    if self.is_nav_paused:
      if not self.change_state_client.wait_for_service(timeout_sec=1.0):
        self.get_logger().error('Nav2 상태 제어 서비스를 찾을 수 없습니다.')
        return

      request = ChangeState.Request()
      request.transition.id = Transition.TRANSITION_ACTIVATE # 노드 재시작 신호
      self.change_state_client.call_async(request)
      self.get_logger().info('Nav2 주행을 다시 시작(Resume) 하였습니다.')
      self.is_nav_paused = False


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
