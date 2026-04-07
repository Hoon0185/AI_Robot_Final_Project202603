import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from std_msgs.msg import String, Bool
from sensor_msgs.msg import BatteryState
from action_msgs.msg import GoalStatus
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType
from protect_product_msgs.msg import DetectionArray # AI 인식 메시지 추가
import yaml
import os
import time
import json
from datetime import datetime
from ament_index_python.packages import get_package_share_directory
from .inventory_db import InventoryDB

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')

        # 0. DB 데이터베이스 초기화
        self.db = InventoryDB()

        # 1. Nav2 Action Client 설정
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # 2. 파라미터 및 프레임 설정
        ns = self.get_namespace().strip('/')
        default_frame = f'{ns}/map' if ns else 'map'
        self.declare_parameter('map_frame', default_frame)
        self.declare_parameter('use_ai_sim', False)
        self.map_frame = self.get_parameter('map_frame').get_parameter_value().string_value
        self.load_shelves()

        # 3. 순찰 상태 관리
        self.current_shelf_idx = 0
        self.is_patrolling = False
        self.current_patrol_id = None # 현재 순찰 세션 ID
        self.last_detection = None
        self.reported_tags = set() # 중복 리포팅 방지를 위한 저장소
        self._goal_handle = None

        # 4. 순찰 및 제어 명령 구독 - 네임스페이스 영향을 받지 않도록 절대 경로(/) 사용
        self.cmd_sub = self.create_subscription(String, '/patrol_cmd', self.cmd_callback, 10)
        self.emergency_sub = self.create_subscription(Bool, '/emergency_stop', self.emergency_callback, 10)
        self.pause_sub = self.create_subscription(Bool, '/pause_patrol', self.pause_callback, 10) # 장애물 노드로부터 일시정지 요청 수신

        # 5. 순찰 상태 발행 (UI용)
        self.patrol_status_pub = self.create_publisher(String, '/patrol_status', 10)
        # 6. 실시간 위치 리포팅 (서버 대시보드용)
        self.current_x = 0.0
        self.current_y = 0.0
        self.pose_received = False # 위치 정보 수신 여부 확인 (0,0 보고 방지)
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped, 'amcl_pose', self.pose_callback, 10)
        self.pose_timer = self.create_timer(2.0, self.report_pose_to_server)

        # 7. AI 인식 연동 (Verifier 노드 데이터 수신)
        self.ai_sub = self.create_subscription(
            DetectionArray, '/verified_objs', self.ai_callback, 10)
        self.latest_ai_barcodes = [] # 최근 인식된 바코드들 저장
        self.latest_ai_class_ids = [] # 최근 인식된 YOLO ID들 저장
        # 8. 위치 초기화 발행 (AMCL 보정용)
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.is_waiting_for_ai = False
        self.ai_wait_start_time = None
        self.is_paused = False # 일시정지 상태 플래그

        # 9. 실시간 배터리 상태 모니터링 (서버 보고)
        self.current_battery = 85.0
        self.battery_sub = self.create_subscription(
            BatteryState, '/battery_state', self.battery_callback, 10)
        self.battery_timer = self.create_timer(15.0, self.report_battery_to_server)
        
        # 10. 원격 설정 동기화 (장애물 대기 시간 등)
        # 초기 성공 시까지 15초 주기로 시도하고, 성공 시 타이머 중단
        self.param_client = self.create_client(SetParameters, '/obstacle_node/set_parameters')
        self.config_sync_timer = self.create_timer(15.0, self.initial_config_sync)
        self.last_avoidance_wait = None # 초기값을 None으로 하여 서버 설정이 10초여도 첫 동기화를 보장함

        # --- [추가] 실행 즉시 최신 설정 강제 동기화 ---
        self.sync_remote_config()

        self.get_logger().info('Patrol Main Node (Server Link Version) started.')

    def load_shelves(self):
        """순찰 포인트 및 시퀀스 로드 (1순위: 원격 DB Plan, 2순위: 로컬 YAML)"""
        try:
            # 단순 위치 목록이 아닌, 웹의 '순찰 제품 및 시퀀스 관리'에서 설정한 정렬된 플랜을 가져옵니다.
            db_plan = self.db.get_active_patrol_plan()
            if db_plan and len(db_plan) > 0:
                self.shelves = db_plan
                self.shelf_list = list(self.shelves.keys())
                self.get_logger().info(f"Successfully loaded {len(self.shelves)} planned waypoints in sequence from Remote DB.")
                return
        except Exception as e:
            self.get_logger().warn(f"Failed to fetch patrol plan from DB: {e}. Falling back to YAML.")

        # 로컬 YAML 폴백
        pkg_dir = get_package_share_directory('patrol_main')
        yaml_path = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')
        if not os.path.exists(yaml_path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            yaml_path = os.path.join(current_dir, '..', 'config', 'shelf_coords.yaml')

        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            if '/**' in config:
                self.shelves = config['/**']['ros__parameters']['shelves']
            else:
                self.shelves = config.get('shelves', {})
        self.shelf_list = list(self.shelves.keys())

    def pause_callback(self, msg):
        if msg.data and self.is_patrolling:
            # 장애물이 감지되었을 때의 처리
            if not self.is_paused:
                self.get_logger().warn('장애물 감지로 인해 현재 목적지 주행을 전면 취소하고 대기합니다.')
                self.is_paused = True

                self.cancel_nav()

        elif not msg.data and self.is_patrolling and self.is_paused:
            self.get_logger().info('대기 시간이 끝나 장애물 상황이 해제되었습니다. 다시 가던 목적지로 출발합니다.')
            self.is_paused = False

            self.resend_current_goal()

    def resend_current_goal(self):
        """서버 세션을 건드리지 않고, 현재 멈춰있는 인덱스의 좌표만 Nav2에 다시 전송합니다."""
        if self.current_shelf_idx >= len(self.shelf_list):
            self.get_logger().warn('다시 보낼 목적지 인덱스가 범위를 벗어났습니다.')
            return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]

        tx, ty, tyaw = float(coords['x']), float(coords['y']), float(coords['yaw'])
        self.get_logger().info(f'--- [재출발] Goal: {shelf_name} ---')
        self.get_logger().info(f'Target Coords: X={tx:.4f}, Y={ty:.4f}, Yaw={tyaw:.4f}')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.map_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = tx
        goal_msg.pose.pose.position.y = ty

        import math
        yaw = float(coords['yaw'])
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self._action_client.wait_for_server()
        self._send_goal_future = self._action_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def emergency_callback(self, msg):
        if msg.data:
            self.get_logger().error('!!! EMERGENCY STOP RECEIVED !!!')
            # 서버에 순찰 종료/중단 세션 등록
            self.db.finish_patrol_session()

            self.is_patrolling = False
            self.cancel_nav()

    def cmd_callback(self, msg):
        cmd = msg.data
        if cmd == 'START_PATROL' and not self.is_patrolling:
            self.get_logger().info('Starting Patrol Sequence (Updating config first...)')
            
            # --- [추가] 순찰 시작 전 최신 설정 강제 동기화 ---
            self.sync_remote_config()
            self.load_shelves()
            
            # 서버에 순찰 시작 세션 등록 및 ID 저장
            self.current_patrol_id = self.db.start_patrol_session()

            self.is_patrolling = True
            self.start_time = datetime.now()
            self.current_shelf_idx = 0
            self.reported_tags.clear() # 새로운 순찰 세션 시작 시 초기화
            self.publish_status('patrolling')
            self.send_next_goal()
        elif cmd == 'RECONFIG':
            self.get_logger().info('[REMOTE] Configuring node based on UI request...')
            self.sync_remote_config()
            self.load_shelves()
        elif cmd == 'RETURN_HOME':
            self.get_logger().info('Returning to Base...')
            # 서버에 순찰 종료 세션 등록 (진행 중이었다면)
            self.db.finish_patrol_session()

            self.is_patrolling = False
            self.cancel_nav()
            self.go_to_origin()
        elif cmd == 'RESET_POSE':
            self.get_logger().info('Moving back to Initial Position (No Jump)...')
            self.go_to_origin()

    def cancel_nav(self):
        """현재 진행 중인 Nav2 액션 목표를 취소합니다."""
        if self._goal_handle is not None:
            self.get_logger().info('Cancelling current navigation goal...')
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None
        else:
            self.get_logger().info('No active navigation goal to cancel.')

    def go_to_origin(self):
        """로봇을 맵의 원점(0,0,0)으로 이동시킵니다."""
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.map_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = 0.0
        goal_msg.pose.pose.position.y = 0.0
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.x = 0.0
        goal_msg.pose.pose.orientation.y = 0.0
        goal_msg.pose.pose.orientation.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0

        self._action_client.wait_for_server()
        self._action_client.send_goal_async(goal_msg)
        self.get_logger().info('Navigating back to HOME (0,0)...')


    def send_next_goal(self):
        if self.current_shelf_idx >= len(self.shelf_list):
            self.get_logger().info('Patrol Completed! Navigating back to HOME (0,0)...')
            # 서버에 순찰 종료 세션 등록
            self.db.finish_patrol_session()

            self.is_patrolling = False
            self.end_time = datetime.now()
            self.publish_status('completed')

            # 모든 순찰 완료 후 원점으로 자동 복귀
            self.go_to_origin()
            return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]

        tx, ty, tyaw = float(coords['x']), float(coords['y']), float(coords['yaw'])
        self.get_logger().info(f'--- Sending Goal: {shelf_name} ---')
        self.get_logger().info(f'Target Coords: X={tx:.4f}, Y={ty:.4f}, Yaw={tyaw:.4f}')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.map_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = tx
        goal_msg.pose.pose.position.y = ty

        import math
        yaw = float(coords['yaw'])
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self._action_client.wait_for_server()
        self._send_goal_future = self._action_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        self._goal_handle = future.result()
        if not self._goal_handle.accepted:
            self.get_logger().error('Goal rejected')
            self.is_patrolling = False
            return
        self._get_result_future = self._goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)
        self.get_logger().info('Goal accepted by Nav2 server.')

    def get_result_callback(self, future):
        # 액션 종료 시 핸들 초기화
        self._goal_handle = None
        status = future.result().status

        if status == GoalStatus.STATUS_CANCELED:
            self.get_logger().info('순찰이 일시 정지되어 주행이 안전하게 취소되었습니다.')
            self.is_patrolling = True
            self.is_paused = True
            return

        if status == GoalStatus.STATUS_SUCCEEDED:
            shelf_name = self.shelf_list[self.current_shelf_idx]
            target_barcode = self.shelves[shelf_name].get('tag_barcode', 'UNKNOWN')

            # 1. AI 시뮬레이션 모드일 때 (카메라 준비 안 됨)
            if self.get_parameter('use_ai_sim').get_parameter_value().bool_value:
                self.get_logger().info(f'[SIM] AI Simulation Mode active for {shelf_name}. Assuming success.')
                detected = target_barcode # 시뮬레이션 성공 가정

                self.last_detection = {
                    "tag_barcode": target_barcode,
                    "detected_barcode": detected,
                    "confidence": 1.0
                }

                if target_barcode not in self.reported_tags:
                    self.db.report_detection(
                        tag_barcode=target_barcode,
                        patrol_id=self.current_patrol_id or 0,
                        waypoint_id=1, # 시뮬레이션 기본 ID
                        x=self.current_x,
                        y=self.current_y,
                        detected_barcode=detected,
                        confidence=1.0
                    )
                    self.reported_tags.add(target_barcode)

                self._delay_timer = self.create_timer(1.0, self.proceed_to_next_shelf)
                return

            # 2. 실제 AI 인식 모드
            self.get_logger().info(f'Arrival at {shelf_name}. Scanned Tag: {target_barcode}. Waiting for AI verification...')

            # AI 인식 대기 모드 진입
            self.is_waiting_for_ai = True
            self.ai_wait_start_time = self.get_clock().now()
            self.latest_ai_barcodes = []

            # 이전에 설정된 타이머가 있다면 제거
            if hasattr(self, '_delay_timer') and self._delay_timer:
                self.destroy_timer(self._delay_timer)
                self._delay_timer = None

            # AI 인식을 최대 8초까지 기다리는 폴링 타이머 가동
            self._delay_timer = self.create_timer(0.5, self.check_ai_result_and_proceed)
        else:
            self.get_logger().error(f'Navigation FAILED with status code: {status}. Stopping patrol for safety.')
            self.is_patrolling = False
            self.publish_status('error')

    def proceed_to_next_shelf(self):
        """대기 타이머 종료 후 다음 목적지로 이동하거나 순찰을 종료함"""
        if hasattr(self, '_delay_timer') and self._delay_timer:
            self.destroy_timer(self._delay_timer)
            self._delay_timer = None

        if not self.is_patrolling:
            self.get_logger().info('Patrol is no longer active. Stopping sequence.')
            return

        self.current_shelf_idx += 1
        self.publish_status('patrolling')
        self.send_next_goal()

    def publish_status(self, status):
        info = {
            'status': status,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'current_x': round(self.current_x, 3), # UI 표시용 소수점 제한
            'current_y': round(self.current_y, 3)
        }

        if status == 'patrolling':
            info['start_time'] = self.start_time.strftime('%Y-%m-%d %H:%M:%S')
            if self.current_shelf_idx < len(self.shelf_list):
                info['current_shelf'] = self.shelf_list[self.current_shelf_idx]
                info['progress'] = f"{self.current_shelf_idx + 1}/{len(self.shelf_list)}"
                if self.last_detection:
                    info['last_detection'] = self.last_detection
        elif status == 'completed':
            info['start_time'] = self.start_time.strftime('%Y-%m-%d %H:%M:%S')
            info['end_time'] = self.end_time.strftime('%Y-%m-%d %H:%M:%S')
            info['total_shelves'] = len(self.shelf_list)

        msg = String()
        msg.data = json.dumps(info, ensure_ascii=False)
        self.patrol_status_pub.publish(msg)

    def pose_callback(self, msg):
        """로봇의 현재 좌표(x, y)를 실시간으로 업데이트"""
        self.current_x = msg.pose.pose.position.x
        self.current_y = msg.pose.pose.position.y
        self.pose_received = True

    def report_pose_to_server(self):
        """정해진 주기(2초)마다 서버로 현재 위치 및 상태 보고 (Keep-alive Heartbeat)"""
        # 위치 정보를 한 번도 받지 못했다면 보고하지 않음 (0,0 보고 방지)
        if not self.pose_received:
            return

        # 상태 결정 로직
        status = "IDLE"
        if self.is_patrolling:
            status = "SCANNING" if self.is_waiting_for_ai else "PATROLLING"

        # 좌표값과 상관없이 로봇이 살아있음을 알리기 위해 무조건 전송 (DB 전송)
        self.db.report_robot_pose(self.current_x, self.current_y, status=status)

        # UI 인터페이스(patrol_interface.py)가 5초 이내 토픽 수신 여부로 온라인 상태를 판별하므로, 지속 발행 추가
        status_for_ui = "patrolling" if self.is_patrolling else "idle"
        self.publish_status(status_for_ui)

    def ai_callback(self, msg):
        """AI 인식 노드로부터 실시간 바코드 및 YOLO ID 리스트 수신"""
        if self.is_waiting_for_ai:
            self.latest_ai_barcodes = msg.barcodes
            self.latest_ai_class_ids = msg.class_ids

    def battery_callback(self, msg):
        """로봇의 배터리 상태를 수신하여 저장 (0.0~1.0 또는 0.0~100.0 대응)"""
        val = float(msg.percentage)
        # 1.0 이하면 표준 규격(0.0~1.0)으로 보고 100을 곱함, 그 이상이면 이미 퍼센트(0~100)임
        self.current_battery = val * 100.0 if val <= 1.0 else val

    def report_battery_to_server(self):
        """서버의 /api/robot/battery 엔드포인트로 배터리 상태 보고"""
        success = self.db.report_battery(self.current_battery)
        if not success:
            self.get_logger().warn("Failed to report battery status to server.")

    def check_ai_result_and_proceed(self):
        """AI 인식 대기 중 매칭 여부를 확인하고 다음 단계 진행"""
        if not self.is_waiting_for_ai: return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        target_info = self.shelves[shelf_name]
        target_barcode = target_info.get('tag_barcode', 'UNKNOWN')
        waypoint_id = target_info.get('waypoint_id', -1)

        found = False
        detected_barcode = ""
        detected_yolo_id = None

        # 1. 최근 인식된 결과 중 타겟 바코드가 있는지 확인
        if target_barcode in self.latest_ai_barcodes:
            found = True
            detected_barcode = target_barcode
            self.get_logger().info(f'[AI] Found matching barcode: {target_barcode}')

        # 2. 바코드가 없고 YOLO ID가 있는 경우 첫 번째 ID를 결과로 채택
        if not found and len(self.latest_ai_class_ids) > 0:
            found = True
            detected_yolo_id = int(self.latest_ai_class_ids[0])
            self.get_logger().info(f'[AI] Found YOLO ID: {detected_yolo_id}')

        # 타임아웃 체크 (8초)
        elapsed = (self.get_clock().now() - self.ai_wait_start_time).nanoseconds / 1e9

        if found or elapsed > 8.0: # 8초 경과 시 강제 종료 혹은 결과 리포팅
            self.is_waiting_for_ai = False

            # 타이머 정리
            if self._delay_timer:
                self.destroy_timer(self._delay_timer)
                self._delay_timer = None

            # 인식 성공 또는 타임아웃에 따른 결과 리포팅
            self.last_detection = {
                "tag_barcode": target_barcode,
                "detected_barcode": detected_barcode if found and detected_barcode else "",
                "yolo_class_id": detected_yolo_id,
                "confidence": 0.99 if found else 0.0
            }

            if target_barcode not in self.reported_tags:
                success, msg = self.db.report_detection(
                    tag_barcode=target_barcode,
                    patrol_id=self.current_patrol_id or 0,
                    waypoint_id=waypoint_id,
                    x=self.current_x,
                    y=self.current_y,
                    detected_barcode=self.last_detection["detected_barcode"] if self.last_detection["detected_barcode"] else None,
                    yolo_class_id=detected_yolo_id,
                    confidence=0.99 if found else 0.0
                )
                if success:
                    self.get_logger().info(f'Reported to DB (Found: {found}): {target_barcode}')
                    self.reported_tags.add(target_barcode)
                else:
                    self.get_logger().warn(f'Failed to report DB: {msg}')

            # 다음 목적으로 이동
            self.proceed_to_next_shelf()

    def proceed_to_next_shelf(self):
        """대기 타이머 종료 후 다음 목적지로 이동하거나 순찰을 종료함"""
        if hasattr(self, '_delay_timer') and self._delay_timer:
            self.destroy_timer(self._delay_timer)
            self._delay_timer = None

        if not self.is_patrolling:
            self.get_logger().info('Patrol is no longer active. Stopping sequence.')
            return

        self.current_shelf_idx += 1
        self.publish_status('patrolling')
        self.send_next_goal()

    def reset_pose_to_origin(self):
        """로봇의 위치 추정치를 (0,0)으로 초기화합니다."""
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = self.map_frame
        msg.header.stamp = self.get_clock().now().to_msg()

        # 위치 (0,0,0)
        msg.pose.pose.position.x = 0.0
        msg.pose.pose.position.y = 0.0
        msg.pose.pose.position.z = 0.0

        # 자세 (정면)
        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = 0.0
        msg.pose.pose.orientation.w = 1.0

    def initial_config_sync(self):
        """최초 구동 시 정보 획득을 시도하며, 성공 시 주기적 타이머를 중단합니다."""
        success = self.sync_remote_config()
        if success:
            self.get_logger().info('Initial configuration synced successfully. Periodic timer stopped.')
            self.config_sync_timer.cancel()

    def sync_remote_config(self):
        """서버에서 순찰 설정을 가져와 각 노드 파라미터에 실시간 반영"""
        config = self.db.get_patrol_config()
        if not config:
            return False

        # 1. 장애물 대기 시간 (avoidance_wait_time) 동기화
        new_wait = config.get('avoidance_wait_time')
        if new_wait is not None:
            new_wait_int = int(new_wait)
            if new_wait_int != self.last_avoidance_wait:
                self.get_logger().info(f'[DB] New Avoidance Wait Time detected: {new_wait_int}s (Syncing to obstacle_node...)')
                
                # obstacle_node의 파라미터명은 'current_wait_time'입니다.
                if self.param_client.wait_for_service(timeout_sec=1.0):
                    req = SetParameters.Request()
                    val = ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=new_wait_int)
                    req.parameters = [Parameter(name='current_wait_time', value=val)]
                    self.param_client.call_async(req)
                    self.last_avoidance_wait = new_wait_int
                    self.get_logger().info(f'[SYNC] Obstacle wait time set to {new_wait_int}s')
                else:
                    self.get_logger().warn('/obstacle_node/set_parameters service not available. Check if obstacle_node is running.')
        
        return True


def main(args=None):
    rclpy.init(args=args)
    node = PatrolNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
