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
        self.db = InventoryDB(base_url="http://16.184.56.119/api")
        
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
        
        # Remote Command Polling
        self.last_cmd_id = None
        try:
            # 시작 시점의 최신 명령 ID를 가져와서 저장 (이전 명령 재실행 방지)
            init_data = self.db.get_latest_command()
            if init_data:
                self.last_cmd_id = init_data.get('command_id')
                self.node.get_logger().info(f"Initialized with last remote command ID: {self.last_cmd_id}")
        except Exception as e:
            self.node.get_logger().error(f"Failed to fetch initial command ID: {e}")

        self.last_cmd_name = None
        self.poll_thread = threading.Thread(target=self._poll_remote_commands, daemon=True)
        self.poll_thread.start()

    def _poll_remote_commands(self):
        """서버 대시보드로부터 원격 명령을 주기적으로 확인합니다."""
        import time
        while rclpy.ok():
            try:
                data = self.db.get_latest_command()
                if data:
                    cmd_name = data.get('command_type') or data.get('command')
                    cmd_id = data.get('command_id')
                    
                    # 새로운 ID의 명령일 경우에만 실행
                    if cmd_id is not None and cmd_id != self.last_cmd_id:
                        self.node.get_logger().info(f"[REMOTE] New command (ID:{cmd_id}): {cmd_name}")
                        self._execute_remote_command(cmd_name)
                        
                        # 실행 직후 즉시 로컬 ID 업데이트하여 중복 실행 방지
                        self.last_cmd_id = cmd_id
                        
                        # 서버에 완료 보고
                        success = self.db.complete_command(cmd_id)
                        if success:
                            self.node.get_logger().info(f"[REMOTE] Command {cmd_id} marked as COMPLETED on server.")
                        else:
                            self.node.get_logger().warn(f"[REMOTE] Failed to mark command {cmd_id} as COMPLETED.")
            except Exception as e:
                self.node.get_logger().error(f"[REMOTE] Polling error: {e}")
            time.sleep(2.0)

    def _execute_remote_command(self, cmd):
        """수신된 원격 명령을 ROS 토픽으로 변환하여 발행합니다."""
        if cmd == "START_PATROL":
            self.trigger_manual_patrol()
        elif cmd == "RETURN_HOME":
            self.return_to_base()
        elif cmd == "EMERGENCY_STOP":
            self.trigger_emergency_stop()
        elif cmd == "RESET_POSE":
            self.reset_position()
        elif cmd == "BUZZER_ON":
            self.trigger_buzzer(True)
        elif cmd == "BUZZER_OFF":
            self.trigger_buzzer(False)

    def _status_cb(self, msg):
        try:
            self.latest_status = json.loads(msg.data)
        except Exception as e:
            self.node.get_logger().error(f"Failed to parse status JSON: {e}")
            self.latest_status = {"data": msg.data}

    def _set_param(self, name, value, param_type):
        """Internal helper to set parameters on the patrol_scheduler node."""
        if not self.param_client.wait_for_service(timeout_sec=2.0):
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
        try:
            twist = Twist()
            speed = 0.2
            turn = 0.5
            
            if direction == "UP":
                twist.linear.x = float(speed)
            elif direction == "DOWN":
                twist.linear.x = float(-speed)
            elif direction == "LEFT":
                twist.angular.z = float(turn)
            elif direction == "RIGHT":
                twist.angular.z = float(-turn)
            elif direction == "STOP":
                twist.linear.x = 0.0
                twist.angular.z = 0.0
            
            p_res = self.teleop_pub.publish(twist)
            print(f"[ROS] Topic /cmd_vel_teleop published: {direction}")
            return True, f"Move command {direction} sent"
        except Exception as e:
            print(f"[ROS ERROR] Failed to move robot: {e}")
            return False, str(e)

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
        """수동 순찰을 즉시 실행합니다. (토픽 방식)"""
        msg = String()
        msg.data = "START_PATROL"
        self.cmd_pub.publish(msg)
        self.node.get_logger().info("[UI] Manual patrol trigger published to /patrol_cmd")
        return True, "Manual patrol trigger sent via topic"

    def get_recent_patrol_time(self):
        """최근 순찰 상태 및 시간 정보를 가져옵니다. (ROS 토픽 우선, 없으면 DB 로그)"""
        if self.latest_status:
            return self.latest_status
        
        # ROS 토픽에 데이터가 없으면 DB에서 최신 로그를 가져옴
        history = self.db.get_patrol_history()
        if history and len(history) > 0:
            latest = history[0]
            return {
                "status": latest.get('status', 'Completed'),
                "start_time": latest.get('start_time', 'No Data'),
                "end_time": latest.get('end_time', '-'),
                "error_found": latest.get('error_found', 0)
            }
        return None

    def get_patrol_history_data(self):
        """DB에서 전체 순찰 이력을 가져옵니다."""
        return self.db.get_patrol_history()

    def get_db_config(self):
        """DB에서 현재 인벤토리/순찰 설정을 가져옵니다."""
        return self.db.get_patrol_config()

    def sync_config_to_db(self, avoidance_wait=10, hour=0, minute=0):
        """현재 설정을 DB 서버에 저장합니다. (시/분 분리 전송)"""
        return self.db.update_patrol_config(avoidance_wait=avoidance_wait, hour=hour, minute=minute)

    def shutdown(self):
        """ROS 노드와 백그라운드 스레드를 안전하게 종료합니다."""
        self.executor.shutdown()
        self.node.destroy_node()
