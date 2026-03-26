import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import json
import threading

class PatrolInterface:
    def __init__(self, node_name='ui_patrol_interface'):
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(node_name)
        
        # Service Clients
        self.trigger_client = self.node.create_client(Trigger, '/trigger_manual_patrol')
        self.param_client = self.node.create_client(SetParameters, '/patrol_scheduler/set_parameters')
        
        # Status Subscriber
        self.latest_status = None
        self.status_sub = self.node.create_subscription(
            String, '/patrol_status', self._status_cb, 10)
            
        # Background spinning for asynchronous communication
        self.executor = rclpy.executors.SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.spin_thread.start()

    def _status_cb(self, msg):
        try:
            self.latest_status = json.loads(msg.data)
        except Exception as e:
            self.node.get_logger().error(f"Failed to parse status JSON: {e}")
            self.latest_status = {"data": msg.data}

    def _set_param(self, name, value, param_type):
        """Internal helper to set parameters on the patrol_scheduler node."""
        if not self.param_client.wait_for_server(timeout_sec=2.0):
            return False, "Parameter service /patrol_scheduler/set_parameters not available"
        
        req = SetParameters.Request()
        val = ParameterValue(type=param_type)
        if param_type == ParameterType.PARAMETER_STRING:
            val.string_value = str(value)
        elif param_type == ParameterType.PARAMETER_DOUBLE:
            val.double_value = float(value)
        elif param_type == ParameterType.PARAMETER_STRING_ARRAY:
            val.string_array_value = [str(v) for v in value]
            
        req.parameters = [Parameter(name=name, value=val)]
        self.param_client.call_async(req)
        return True, f"Request to set {name} sent"

    # Public API Methods
    
    def set_patrol_interval(self, minutes: float):
        """순찰 간격(분)을 설정합니다."""
        return self._set_param('patrol_interval_min', float(minutes), ParameterType.PARAMETER_DOUBLE)

    def set_patrol_mode(self, mode: str):
        """순찰 모드('periodic' 또는 'scheduled')를 설정합니다."""
        return self._set_param('patrol_mode', mode, ParameterType.PARAMETER_STRING)

    def set_start_time(self, ref_time: str):
        """주기 순찰의 시작 기준 시간(HH:MM)을 설정합니다."""
        return self._set_param('reference_time', ref_time, ParameterType.PARAMETER_STRING)

    def set_scheduled_times(self, times: list):
        """예약 순찰 시간 목록(['HH:MM', ...])을 설정합니다."""
        return self._set_param('scheduled_times', times, ParameterType.PARAMETER_STRING_ARRAY)

    def trigger_manual_patrol(self):
        """수동 순찰을 즉시 실행합니다."""
        if not self.trigger_client.wait_for_server(timeout_sec=2.0):
            return False, "Service /trigger_manual_patrol not available"
        self.trigger_client.call_async(Trigger.Request())
        return True, "Manual patrol trigger sent"

    def get_recent_patrol_time(self):
        """최근 순찰 상태 및 시간 정보를 가져옵니다."""
        return self.latest_status

    def shutdown(self):
        """ROS 노드와 백그라운드 스레드를 안전하게 종료합니다."""
        self.executor.shutdown()
        self.node.destroy_node()
        # Note: rclpy.shutdown() depends on whether the user wants to close the whole system
