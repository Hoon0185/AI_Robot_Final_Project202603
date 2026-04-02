import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist, PointStamped
from nav_msgs.msg import Odometry, OccupancyGrid
from nav2_msgs.srv import ClearEntireCostmap
import tf2_ros
from tf2_geometry_msgs import do_transform_point
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

    # ---- TF2 및 지도 구독 설정 ----
    self.tf_buffer = tf2_ros.Buffer()
    self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
    self.map_data = None
    
    qos_profile_map = QoSProfile(
      reliability=ReliabilityPolicy.RELIABLE,
      history=HistoryPolicy.KEEP_LAST,
      depth=1
    )
    self.map_sub = self.create_subscription(
      OccupancyGrid,
      '/map',
      self.map_callback,
      qos_profile_map
    )

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
    
    # 히스테리시스 적용 거리
    self.safe_distance_enter = 0.40 # 진입 (벽 제외 새로운 장애물 40cm 이내)
    self.safe_distance_exit = 0.55 # 해제 (55cm 이상 멀어져야 해제)
    
    self.min_front_dist = 9.9 
    self.wait_time_s = self.get_parameter('obstacle_wait_time').get_parameter_value().integer_value

    self.current_x = 0.0
    self.current_y = 0.0

  def map_callback(self, msg):
    self.map_data = msg
    self.get_logger().info(f'[Map] 지도 데이터 수신 완료. Resolution: {msg.info.resolution}m')

  def odom_callback(self, msg):
    self.current_x = msg.pose.pose.position.x
    self.current_y = msg.pose.pose.position.y

  def scan_callback(self, msg):
    if self.map_data is None:
        return # 지도 데이터가 없으면 필터링 불가

    try:
        # map -> laser_frame 변환 정보 획득
        now = rclpy.time.Time()
        trans = self.tf_buffer.lookup_transform('map', msg.header.frame_id, now)
    except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
        return

    # 전방 60도 범위의 센서 데이터 추출
    # (일부 주석 처리된 0:30, 330:360은 일반적인 LDS-01 기준)
    angles = list(range(0, 31)) + list(range(329, 360))
    
    unknown_obstacles = []

    for angle in angles:
        if angle >= len(msg.ranges): continue
        dist = msg.ranges[angle]
        if not (0.1 < dist < 3.0): continue

        # 1. 라이다 좌표계의 점을 지도 좌표계로 변환
        angle_rad = math.radians(angle) if angle <= 180 else math.radians(angle - 360)
        point_laser = PointStamped()
        point_laser.header = msg.header
        point_laser.point.x = dist * math.cos(angle_rad)
        point_laser.point.y = dist * math.sin(angle_rad)
        point_laser.point.z = 0.0

        point_map = do_transform_point(point_laser, trans)
        
        # 2. 지도에서의 인덱스 계산
        mx = int((point_map.point.x - self.map_data.info.origin.position.x) / self.map_data.info.resolution)
        my = int((point_map.point.y - self.map_data.info.origin.position.y) / self.map_data.info.resolution)

        if 0 <= mx < self.map_data.info.width and 0 <= my < self.map_data.info.height:
            map_index = mx + (my * self.map_data.info.width)
            occ_value = self.map_data.data[map_index]
            
            # 지도 수치가 50 이상이면 이미 기록된 정적 벽으로 판단하여 제외
            if occ_value > 50:
                continue
            
            # 빈 공간(0~10) 또는 알 수 없음(255)인데 물체가 있다면 동적 장애물
            unknown_obstacles.append(dist)

    # 실시간 전방 거리 최소값 업데이트 (동적 장애물 기준)
    if unknown_obstacles:
      self.min_front_dist = min(unknown_obstacles)
    else:
      self.min_front_dist = 9.9

    # 우회 시퀀스 수행 중이거나 안정화 단계에서는 센서 감지 무시
    if self.wait_counter < 0 or self.recovery_counter > 0:
      return

    # 히스테리시스 기반 정지/해제 판단
    min_dist = self.min_front_dist
    if min_dist < self.safe_distance_enter:
      if not self.is_blocked:
        self.get_logger().warn(f'동적 장애물 감지! 거리: {min_dist:.2f}m (지도의 벽 제외)')
        self.is_blocked = True
        self.wait_counter = 0
    elif min_dist > self.safe_distance_exit:
      if self.is_blocked:
        # 이미 감지된 상태에서 대기 시간을 채우지 않았더라도 너무 멀어지면 수동 해제 가능 여부 고민 (현재는 시간 채우기 유지)
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
        self.get_logger().info(f'[Blocked] 동적 장애물 대기 중... {seconds}s / {self.wait_time_s}s')

      if self.wait_counter >= max_count:
        self.get_logger().info(f'{self.wait_time_s}초 경과. 동적 우회 시퀀스를 시작합니다.')
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
        self.get_logger().warn(f'[DB] 서버 통신 지연 (확인 중...)', once=True)

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
