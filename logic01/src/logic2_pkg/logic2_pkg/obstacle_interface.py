import rclpy
from rclpy.node import Node
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import threading
import datetime # 저장 시간대 기록 - DB에서 필요 없으면 제거

class ObstacleInterface:
  def __init__(self, node_name='ui_obstacle_interface'):
    if not rclpy.ok():
      rclpy.init()
    self.node = Node(node_name)

    # ---- 서비스 클라이언트 설정 ----
    self.param_client = self.node.create_client(
      SetParameters,
      'obstacle_node/set_parameters'
    )

    # ---- 기본값 및 상태 관리 변수 ----
    self.current_wait_time = 10 #  기본 대기 시간(초)
    self.is_db_connected = False # DB 연결 상태
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
      # ---- DB 연결 시도 ----
      # TODO: 실제 DB 연결 시 성공 여부에 따라 True/False 설정
      self.is_db_connected = False # 임시로 True/False 변형해가며 실행

      if self.is_db_connected:
        db_value = 5 # TODO: DB에서 실제 대기 시간 값을 가져와서 설정
        self.current_wait_time = db_value
        self.set_wait_time(db_value) # 노드에 초기값 전송
        self.node.get_logger().info(f"DB 연결 성공: 현재 대기시간 {db_value}초")
      else:
        self.node.get_logger().warn("DB 연결 실패: 기본 대기시간 10초를 사용합니다.")

    except Exception as e:
      self.node.get_logger().error(f"DB 초기 연결 예외 발생: {e}")
      self.is_db_connected = False


  def update_db_and_sync(self, seconds:int):
    """
    UI 슬라이더에서 대기 시간 변경 -> DB 업데이트 및 노드 전송을 동시에 처리하는 함수
    """
    self.current_wait_time = int(seconds)
    save_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # 저장 시간대 기록

    # ---- 로봇 노드 파라미터 전송 ----
    ros_success, _ = self.set_wait_time(self.current_wait_time)

    # ---- DB 저장 시도 ----
    db_success, db_msg = self.save_to_db(self.current_wait_time, save_time)

    if ros_success and db_success:
      self.node.get_logger().info(f"성공: {seconds}초 설정 / DB 저장 완료 ({save_time})")
      return True, f"성공: {seconds}초 설정 / DB 저장 완료 ({save_time})"

    elif not ros_success and db_success:
      self.node.get_logger().warn(f"경고: 대기 시간 {seconds}초 설정 실패 / DB 저장 성공")
      return False, f"경고: 대기 시간 {seconds}초 설정 실패 / DB 저장 성공"

    elif ros_success and not db_success:
      self.node.get_logger().warn(f"경고: 대기 시간 {seconds}초 설정 완료 / DB 저장 실패: 재전송 예정")
      self.pending_data = {"value": seconds, "timestamp": save_time} # 대기 시간 임시 저장
      return False, f"경고: 대기 시간 {seconds}초 설정 완료 / DB 저장 실패: 재전송 예정"

    else:
      self.node.get_logger().error("시스템 마비: 로봇 및 DB 통신 실패. 전체 시스템 연결을 확인해주세요.")
      return False, "전체 시스템 연결을 확인해주세요."


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


  def save_to_db(self, seconds:int, timestamp:str):
    """
    장애물 대기 시간과 저장 시간대를 DB에 저장하는 함수
    """
    if self.is_db_connected:
      # TODO : 실제 DB 저장 로직 구현 필요
      # DB 저장 코드 작성 예시
      # table  = self.server.send_log(
      #   log_type="obstacle_wait_time",
      #   value=seconds,
      #   timestamp=timestamp
      # )
      return True, "DB에 저장되었습니다."
    else:
      return False, "DB 연결이 되어 있지 않습니다. 저장에 실패했습니다."

  def check_pending_data(self):
    """
    DB 연결이 복구되었는지 확인하고, DB 저장에 실패한 장애물 대기 시간 데이터를 재전송하는 함수
    """
    if self.pending_data and self.is_db_connected: # DB 연결 복구 및 저장 대기 데이터 존재 여부 확인
      val = self.pending_data["value"]
      ts = self.pending_data["timestamp"]

      # DB 저장 재시도
      success, _ = self.save_to_db(val, ts)
      if success:
        self.node.get_logger().info(f"재시도 성공: 누락되었던 대기시간 {val}초가 DB에 저장되었습니다.")
        self.pending_data = None # 임시 데이터 초기화

