import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from geometry_msgs.msg import Twist
from std_srvs.srv import Trigger
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
import json
import threading
import time
from .inventory_db import InventoryDB

class PatrolInterface:
    def __init__(self, node_name='ui_patrol_interface'):
        if not rclpy.ok():
            rclpy.init()
        self.node = Node(node_name)

        # Database & Server Sync
        self.db = InventoryDB(base_url="http://16.184.56.119")#16.184.56.119

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
        self.heartbeat_sub = self.node.create_subscription(
            Bool, '/robot_heartbeat', self._heartbeat_cb, 10)

        self.last_status_received_time = 0.0
        self.last_robot_heartbeat_time = 0.0

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

        # Remote Config Sync Loop (Interval, Start/End, etc.)
        self.remote_interval_min = None
        self.config_sync_thread = threading.Thread(target=self._sync_remote_config, daemon=True)
        self.config_sync_thread.start()

    def _poll_remote_commands(self):
        """서버 대시보드로부터 원격 명령을 주기적으로 확인합니다."""
        import time
        self.processed_ids = set() # 이미 처리한 중복 ID 방어용
        while rclpy.ok():
            try:
                data = self.db.get_latest_command()
                if data:
                    cmd_name = data.get('command_type') or data.get('command')
                    cmd_id = str(data.get('command_id') or "")

                    # 1. ID 중복 체크 (로컬 블랙리스트 및 마지막 ID 비교)
                    is_duplicate_id = (cmd_id == str(self.last_cmd_id) if self.last_cmd_id else False) or (cmd_id in self.processed_ids)
                    if not cmd_id or is_duplicate_id:
                        time.sleep(2.0)
                        continue

                    # 2. 명령 종류별 디바운스 체크 (10초 쿨타임)
                    now = time.time()
                    last_exec_time = self.last_command_execution_times.get(cmd_name, 0)
                    if (now - last_exec_time) < 10.0:
                        self.node.get_logger().info(f"[DEBOUNCE] Skipping {cmd_name} as it was recently executed. Marking as DONE.")
                        # 실행은 건너뛰되, 서버에는 완료 보고를 하여 명령이 계속 남지 않게 함
                        self.db.complete_command(cmd_id)
                        self.last_cmd_id = cmd_id
                        self.processed_ids.add(cmd_id)
                        continue

                    self.node.get_logger().info(f"[REMOTE] Executing command (ID: {cmd_id}, Name: {cmd_name})")

                    # 3. 명령 실행
                    self._execute_remote_command(cmd_name)

                    # 4. 상태 업데이트
                    self.last_cmd_id = cmd_id
                    self.processed_ids.add(cmd_id)
                    self.last_command_execution_times[cmd_name] = now

                    # 5. 서버에 완료 보고
                    success = self.db.complete_command(cmd_id)
                    if success:
                        self.node.get_logger().info(f"[REMOTE] Command {cmd_id} marked as COMPLETED on server.")
                    else:
                        self.node.get_logger().warn(f"[REMOTE] Fail to mark {cmd_id} as COMPLETED. Local lock is active.")
            except Exception as e:
                self.node.get_logger().error(f"[REMOTE] Polling error: {e}")
            time.sleep(2.0)

    def _execute_remote_command(self, cmd):
        """수신된 원격 명령을 ROS 토픽으로 변환하여 발행합니다."""
        if cmd == "START_PATROL":
            self.trigger_manual_patrol()
        elif cmd == "RETURN_HOME" or cmd == "RETURN_TO_BASE":
            self.return_to_base()
        elif cmd == "EMERGENCY_STOP":
            self.trigger_emergency_stop()
        elif cmd == "RESET_POSE":
            self.reset_position()
        elif cmd == "BUZZER_ON":
            self.trigger_buzzer(True)
        elif cmd == "BUZZER_OFF":
            self.trigger_buzzer(False)

    def _sync_remote_config(self):
        """서버 대시보드로부터 순찰 설정을 주기적으로 확인하여 노드에 반영합니다."""
        import time
        while rclpy.ok():
            try:
                config = self.db.get_patrol_config()
                if config:
                    # 1. 순찰 간격 동기화
                    h = config.get('interval_hour', 0)
                    m = config.get('interval_minute', 0)
                    new_interval = float(h * 60 + m)

                    if new_interval > 0 and new_interval != self.remote_interval_min:
                        self.node.get_logger().info(f"[SYNC] New patrol interval from DB: {new_interval} min")
                        success, res = self.set_patrol_interval(new_interval)
                        if success:
                            self.remote_interval_min = new_interval
                            self.node.get_logger().info(f"[SYNC] Successfully updated /patrol_scheduler parameter.")

            except Exception as e:
                self.node.get_logger().error(f"[SYNC] Config sync error: {e}")

            # 10초마다 확인
            time.sleep(10.0)

    def _status_cb(self, msg):
        try:
            self.latest_status = json.loads(msg.data)
            import time
            self.last_status_received_time = time.time()
        except Exception as e:
            self.node.get_logger().error(f"Failed to parse status JSON: {e}")
            self.latest_status = {"data": msg.data}

    def _heartbeat_cb(self, msg):
        """로봇 하드웨어로부터 직접 오는 하트비트 수신"""
        if msg.data:
            self.last_robot_heartbeat_time = time.time()

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
        """부저를 단순히 켜거나 끕니다."""
        msg = Bool()
        msg.data = state
        self.buzzer_pub.publish(msg)
        return True, f"Buzzer {'ON' if state else 'OFF'} sent"

    def beep_buzzer(self, count: int = 3, duration: float = 0.2):
        """부저를 삐, 삐, 삐 형태로 지정된 횟수만큼 울립니다. (비동기 처리)"""
        def run_beep():
            for i in range(count):
                # 부저 켜기
                msg_on = Bool()
                msg_on.data = True
                self.buzzer_pub.publish(msg_on)
                time.sleep(duration)

                # 부저 끄기
                msg_off = Bool()
                msg_off.data = False
                self.buzzer_pub.publish(msg_off)

                # 비프음 사이 간격 (마지막 회차 제외)
                if i < count - 1:
                    time.sleep(0.1)

        # UI 스레드를 방해하지 않도록 별도 스레드에서 실행
        beep_thread = threading.Thread(target=run_beep, daemon=True)
        beep_thread.start()
        return True, f"Buzzer beep sequence started ({count} times)"

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
        """최근 순찰 상태 및 시간 정보를 가져옵니다. (DB 로그 시간 기준 + ROS 실시간 상태 덮어쓰기)"""
        res = {}
        history = self.db.get_patrol_history()

        # 1. DB에서 가장 최근에 있었던 순찰의 시간 정보를 기본으로 가져옴
        if history and len(history) > 0:
            latest = history[0]
            db_start_time = latest.get('start_time') or 'No Data'
            res = {
                "status": latest.get('status', 'Completed'),
                "start_time": db_start_time,
                "end_time": latest.get('end_time', '-'),
                "error_found": latest.get('error_found', 0)
            }

        # 2. 로봇이 실시간 토픽(latest_status)을 쏘고 있다면 상태(status)와 세부 정보를 최신으로 덮어씀
        if self.latest_status:
            topic_status = self.latest_status.get("status")

            # 토픽 상태가 유의미할 때만(순찰 중이거나 에러 등) DB 정보를 덮어씀
            # 'idle'인 경우엔 DB에 기록된 마지막 'Completed' 등의 기록을 보여주는 것이 더 정확함
            if topic_status and topic_status not in ["idle", "IDLE"]:
                res["status"] = topic_status

                # 토픽에 시간 정보가 있다면 DB 정보보다 우선 (진행 중인 세션 표시용)
                topic_start_time = self.latest_status.get("start_time")
                if topic_start_time and topic_start_time != 'No Data':
                    res["start_time"] = topic_start_time

            if res.get("status") == "patrolling" and "current_shelf" in self.latest_status:
                res["current_shelf"] = self.latest_status["current_shelf"]
                res["progress"] = self.latest_status.get("progress", "")

        return res if res else None

    def is_robot_online(self):
        """최근 5초 이내에 상태 메시지 혹은 하트비트를 수신했는지 확인합니다."""
        now = time.time()
        status_online = (now - self.last_status_received_time) < 5.0 if self.last_status_received_time > 0 else False
        heartbeat_online = (now - self.last_robot_heartbeat_time) < 5.0 if self.last_robot_heartbeat_time > 0 else False

        return status_online or heartbeat_online

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
