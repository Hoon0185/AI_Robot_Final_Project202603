import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist
from std_srvs.srv import Trigger
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import json
import threading
from .inventory_db import InventoryDB

class PatrolInterface:
    def __init__(self, node_name='ui_patrol_interface'):
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(node_name)
        
        # Database & Server Sync
        self.db = InventoryDB(base_url="http://localhost:8000")
        
        # Service Clients
        self.trigger_client = self.node.create_client(Trigger, '/trigger_manual_patrol')
        self.param_client = self.node.create_client(SetParameters, '/patrol_scheduler/set_parameters')
        
        # Publishers (Manual Control)
        # LOGIC_02의 twist_mux 우선순위에 따라 /cmd_vel_teleop 사용
        self.teleop_pub = self.node.create_publisher(Twist, '/cmd_vel_teleop', 10)
        self.buzzer_pub = self.node.create_publisher(Bool, '/robot_buzzer', 10)
        self.emergency_pub = self.node.create_publisher(Bool, '/emergency_stop', 10)
        self.cmd_pub = self.node.create_publisher(String, '/patrol_cmd', 10)
        
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

    # --- Public API Methods (UI/Logic 연동용) ---
    
    def move_robot(self, direction: str):
        """수동 이동 명령을 /cmd_vel_teleop 토픽으로 발행합니다."""
        twist = Twist()
        speed = 0.2
        turn = 0.5
        
        if direction == "UP":
            twist.linear.x = speed
        elif direction == "DOWN":
            twist.linear.x = -speed
        elif direction == "LEFT":
            twist.angular.z = turn
        elif direction == "RIGHT":
            twist.angular.z = -turn
        elif direction == "STOP":
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            
        self.teleop_pub.publish(twist)
        return True, f"Move command {direction} sent"

    def trigger_buzzer(self, state: bool = True):
        """부저를 켜거나 끕니다."""
        msg = Bool()
        msg.data = state
        self.buzzer_pub.publish(msg)
        return True, f"Buzzer {'ON' if state else 'OFF'} sent"

    def trigger_emergency_stop(self):
        """비상 정지 신호를 발행합니다."""
        msg = Bool()
        msg.data = True
        self.emergency_pub.publish(msg)
        return True, "Emergency stop signal sent"

    def return_to_base(self):
        """순찰을 중단하고 원점으로 복귀 명령을 내립니다."""
        msg = String()
        msg.data = "RETURN_HOME"
        self.cmd_pub.publish(msg)
        return True, "Return to base command sent"

    def reset_position(self):
        """로봇의 위치 추정치를 초기화하거나 처음 위치로 리셋합니다."""
        msg = String()
        msg.data = "RESET_POSE"
        self.cmd_pub.publish(msg)
        return True, "Reset position command sent"

    def get_inventory_data(self):
        """DB에서 재고 리스트를 가져옵니다. (6개 컬럼 형식)"""
        return self.db.get_inventory()

    def get_alarm_data(self):
        """DB에서 재고 부족 알림 리스트를 가져옵니다. (4개 컬럼 형식)"""
        return self.db.get_alarms()

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
