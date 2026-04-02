import rclpy
from rclpy.node import Node
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import threading
from .inventory_db import InventoryDB

class ObstacleInterface:
  def __init__(self, node_name='ui_obstacle_interface'):
    if not rclpy.ok():
      rclpy.init()
    self.node = Node(node_name)

    self.db = InventoryDB(base_url="http://16.184.56.119/api")

    # ---- 서비스 클라이언트 설정 ----
    self.param_client = self.node.create_client(
      SetParameters,
      'obstacle_node/set_parameters'
    )

    # ---- 기본값 및 상태 관리 변수 ----
    self.current_wait_time = 5 #  기본 대기 시간(초)
    self.pending_data = None # DB 저장에 실패한 임시데이터 저장 변수

    # ---- DB 저장 실패 재시도 타이머 설정 (10초) ----
    self.retry_timer = self.node.create_timer(10.0, self.check_pending_data)

    self.sync_initial_value() # DB 초기값 동기화

    # ---- 멀티 스레드 실행 설정 (비동기) ----
    self.executor = rclpy.executors.SingleThreadedExecutor()
    self.executor.add_node(self.node)
    self.spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
    self.spin_thread.start()

  def sync_initial_value(self):
    """
    초기 구동 시 DB 접속 시도 후 장애물 대기 시간 값을 가져오는 함수
    """
    try:
      config = self.db.get_patrol_config()

      if config:
        db_value = config.get('avoidance_wait_time', self.current_wait_time) # DB에서 대기시간 추출, 없으면 기본값 5초 사용

        self.current_wait_time = int(db_value)
        self.set_wait_time(self.current_wait_time) # 로봇 노드에 적용
        self.node.get_logger().info(f"[API] 초기값 동기화 성공: {self.current_wait_time}초")
      else:
        self.node.get_logger().warn("서버 응답 에러: 기본 대기시간 5초를 사용합니다.")

    except Exception as e:
      self.node.get_logger().error(f"[API] 서버 연결 실패: {e}")


  def update_db_and_sync(self, seconds:int):
    """
    UI 슬라이더에서 대기 시간 변경 -> DB 업데이트 및 노드 전송을 동시에 처리하는 함수
    """
    self.current_wait_time = int(seconds)

    # ---- 로봇 노드 파라미터 전송 ----
    ros_success, _ = self.set_wait_time(self.current_wait_time)

    db_success = False
    try:
      # ---- DB에서 현재 설정값 가져오기 (동기화 목적) ----
      current_config = self.db.get_patrol_config() or {}

      db_success = self.db.update_patrol_config(
        avoidance_wait=self.current_wait_time,
        start=current_config.get("patrol_start_time", "09:00"),
        end=current_config.get("patrol_end_time", "22:00"),
        hour=int(current_config.get("interval_hour", 0)),
        minute=int(current_config.get("interval_minute", 0))
      )
    except Exception as e:
      self.node.get_logger().error(f"[API] 서버 전송 실패: {e}")


    # 결과 분기 처리
    if ros_success and db_success:
      self.node.get_logger().info(f"성공: {seconds}초 설정 및 서버 저장 완료")
      return True, f"성공: {seconds}초 설정 및 서버 저장 완료"

    elif ros_success and not db_success:
      self.node.get_logger().warn(f"경고: {seconds}초 설정 완료 / 서버 저장 실패: 대기열 등록")
      self.pending_data = {"value": seconds}
      return False, f"경고: {seconds}초 설정 완료 / 서버 저장 실패: 재전송 예정"

    else:
      return False, "설정 실패: 전체 시스템 연결을 확인해주세요."


  def set_wait_time(self, seconds: int):
    """
    obstacle_node의 파라미터를 변경하는 함수 (비동기)
    """
    if not self.param_client.wait_for_service(timeout_sec=2.0):
      return False, "서비스를 이용할 수 없습니다. obstacle_node 노드를 확인하세요."

    req = SetParameters.Request()
    val = ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(seconds))
    req.parameters = [Parameter(name='obstacle_wait_time', value=val)]
    self.param_client.call_async(req)
    return True, f"대기 시간이 {seconds}s로 설정되었습니다."


  def check_pending_data(self):
    """
    DB 연결이 복구되었는지 확인하고, DB 저장에 실패한 장애물 대기 시간 데이터를 재전송하는 함수
    """
    if self.pending_data:
      val = self.pending_data["value"]
      try:
        current_config = self.db.get_patrol_config() or {}

        success = self.db.update_patrol_config(
          avoidance_wait=int(val),
          start=current_config.get("patrol_start_time", "09:00"),
          end=current_config.get("patrol_end_time", "22:00"),
          hour=int(current_config.get("interval_hour", 0)),
          minute=int(current_config.get("interval_minute", 0))
        )

        if success:
          self.node.get_logger().info(f"재시도 성공: 누락되었던 {val}초가 서버에 저장되었습니다.")
          self.pending_data = None
      except:
        pass

