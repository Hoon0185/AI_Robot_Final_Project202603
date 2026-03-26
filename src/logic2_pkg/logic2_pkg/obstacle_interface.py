import rclpy
from rclpy.node import Node
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import threading

class ObstacleInterface:
  def __init__(self, node_name='ui_obstacle_interface'):
    if not rclpy.ok():
      rclpy.init()
    self.node = Node(node_name)

    self.param_client = self.node.create_client(
      SetParameters,
      'obstacle_manager/set_parameters'
    )

    self.executor = rclpy.executors.SingleThreadedExecutor()
    self.executor.add_node(self.node)
    self.spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
    self.spin_thread.start()

  def set_wait_time(self, seconds: int):
    """
    UI 슬라이더 값을 받아 노드에 전달하는 함수
    """
    if not self.param_client.wait_for_service(timeout_sec=2.0):
      return False, "서비스를 이용할 수 없습니다. obstacle_manager 노드를 확인하세요."

    req = SetParameters.Request()
    val = ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(seconds))
    req.parameters = [Parameter(name='obstacle_wait_time', value=val)]
    self.param_client.call_async(req)
    return True, f"대기 시간이 {seconds}s로 설정되었습니다."
