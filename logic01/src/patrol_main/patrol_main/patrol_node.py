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
import math
import threading
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

        # 5. 순찰 상태 발행 (UI용)
        self.patrol_status_pub = self.create_publisher(String, '/patrol_status', 10)
        # 6. 실시간 위치 리포팅 (서버 대시보드용)
        self.current_x = 0.0
        self.current_y = 0.0
        self.pose_received = False # 위치 정보 수신 여부 확인 (0,0 보고 방지)
        self.pose_sub = self.create_subscription(
            PoseWithCovarianceStamped, 'amcl_pose', self.pose_callback, 10)
        self.pose_timer = self.create_timer(3.0, self.report_pose_to_server)

        # 7. AI 인식 연동 (Verifier 노드 데이터 수신)
        self.ai_sub = self.create_subscription(
            DetectionArray, '/verified_objs', self.ai_callback, 10)
        self.latest_ai_barcodes = [] # 최근 인식된 바코드들 저장
        self.latest_ai_class_ids = [] # 최근 인식된 YOLO ID들 저장
        self.ai_mode_pub = self.create_publisher(Bool, '/ai_mode', 10) # AI 모드 제어 발행자 추가
        self.target_product_pub = self.create_publisher(String, '/target_product', 10) # [추가] 목표 상품 바코드 전송
        # 8. 위치 초기화 발행 (AMCL 보정용)
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.is_waiting_for_ai = False
        self.ai_wait_start_time = None
        self.ai_wait_timeout = 8.0 # 기본 대기 시간 (서버 설정 로드 전)
        self.is_paused = False # 일시정지 상태 플래그

        # 9. 실시간 배터리 상태 모니터링 (서버 보고)
        self.current_battery = 85.0
        self.battery_sub = self.create_subscription(
            BatteryState, '/battery_state', self.battery_callback, 10)
        self.battery_timer = self.create_timer(15.0, self.report_battery_to_server)
        
        # 10. 주행 재시도 제어 (무한 루프 방지용)
        self._is_handling_retry = False
        self.retry_timer = None

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

                # [추가] DB에서 가져온 최신 좌표를 로컬 YAML 파일에 동기화(저장)
                self.save_shelves_to_yaml()

                # [추가] 서버에서 순찰 설정(대기 시간 등) 로드
                config = self.db.get_patrol_config()
                if config:
                    self.ai_wait_timeout = float(config.get('avoidance_wait_time', 8.0))
                    self.get_logger().info(f"[DB] 서버 순찰 설정 로드 성공. AI 대기시간: {self.ai_wait_timeout}초")

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

    def save_shelves_to_yaml(self):
        """현재 메모리에 있는 선반 좌표를 shelf_coords.yaml 파일에 저장합니다."""
        try:
            # 저장 경로 설정: 소스 코드 위치 우선 탐색
            pkg_dir = get_package_share_directory('patrol_main')
            yaml_path = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')

            # ROS 2 파라미터 표준 형식으로 데이터 구조화
            yaml_data = {
                '/**': {
                    'ros__parameters': {
                        'shelves': self.shelves
                    }
                }
            }

            with open(yaml_path, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False)

            self.get_logger().info(f"Successfully synchronized webDB coordinates to {yaml_path}")

        except Exception as e:
            self.get_logger().error(f"Failed to save shelves to YAML: {e}")

    def resend_current_goal_with_delay(self):
        """로봇이 주춤거리거나 주행 시작 직후 터지는 현상을 막아주는 안정화 장치"""
        if self.retry_timer:
            self.destroy_timer(self.retry_timer)
            self.retry_timer = None
        self.resend_current_goal()


    def resend_current_goal(self):
        """서버 세션을 건드리지 않고, 현재 멈춰있는 인덱스의 좌표만 Nav2에 다시 전송합니다."""
        if self._is_handling_retry:
            return
            
        if self.current_shelf_idx >= len(self.shelf_list):
            self.get_logger().warn('다시 보낼 목적지 인덱스가 범위를 벗어났습니다.')
            return

        self._is_handling_retry = True
        
        # 이전 타이머 정리
        if self.retry_timer:
            self.destroy_timer(self.retry_timer)
            self.retry_timer = None

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]

        tx, ty, tyaw = float(coords['x']), float(coords['y']), float(coords['yaw'])
        self.get_logger().info(f'--- [안정화 재출발] Goal: {shelf_name} ---')
        self.get_logger().info(f'Target Coords: X={tx:.4f}, Y={ty:.4f}, Yaw={tyaw:.4f}')
        
        # 0.5초 후 실제 전송 (메시지 폭주 방지용 일회성 타이머)
        self._resend_timer_internal = self.create_timer(0.5, self._execute_resend)

    def _trigger_retry(self):
        """3초 대기 후 실제 재시도 함수를 호출합니다."""
        if self.retry_timer:
            self.destroy_timer(self.retry_timer)
            self.retry_timer = None
        self.resend_current_goal()

    def _execute_resend(self):
        """실제로 Nav2에 목표를 전송합니다. 실행 직후 타이머를 파괴하여 일회성 동작을 보장합니다."""
        if hasattr(self, '_resend_timer_internal') and self._resend_timer_internal:
             self.destroy_timer(self._resend_timer_internal)
             self._resend_timer_internal = None
        
        if self.current_shelf_idx >= len(self.shelf_list):
            return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]
        tx, ty = float(coords['x']), float(coords['y'])
        
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
            self.get_logger().info('[상태 변경] 긴급 정지(EMERGENCY) 수신으로 순찰을 종료합니다.')
            self.is_patrolling = False
            self.cancel_nav()

    def cmd_callback(self, msg):
        cmd = msg.data
        if cmd == 'START_PATROL' and not self.is_patrolling:
            self.get_logger().info('Starting Patrol Sequence (Updating config first...)')

            # --- [추가] 순찰 시작 전 유령 주행 명령(복귀 등) 강제 청소 ---
            self.cancel_nav()

            # --- [추가] 순찰 시작 전 최신 설정 강제 동기화 ---
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
            self.load_shelves()
        elif cmd == 'RETURN_HOME':
            self.get_logger().info('Returning to Base...')
            # 서버에 순찰 종료 세션 등록 (진행 중이었다면)
            self.db.finish_patrol_session()
            self.get_logger().info('[상태 변경] 복귀(RETURN_HOME) 명령으로 순찰을 종료합니다.')
            self.is_patrolling = False
            self.cancel_nav()
            self.go_to_origin()
        elif cmd == 'RESET_POSE':
            self.get_logger().info('Moving back to Initial Position (No Jump)...')
            self.go_to_origin()

    def cancel_nav(self):
        """현재 진행 중인 Nav2 액션 목표를 실제로 취소합니다."""
        if self._goal_handle is not None:
            self.get_logger().info('Cancelling current navigation goal asynchronously...')
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
            self.get_logger().info('[상태 변경] 모든 선반 순찰이 완료되어 순찰을 종료합니다.')
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
            self.get_logger().error('[상태 변경] Nav2 서버가 목표를 거절하여 순찰을 중단합니다.')
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
            self.get_logger().info('Navigation goal was cancelled successfully.')
            # 취소 시에는 순찰 상태를 꼬이게 하지 않고 조용히 리턴합니다.
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
            self.latest_ai_data = None # 이전 데이터 초기화
            self.ai_mode_pub.publish(Bool(data=True)) # 통합 AI 노드 활성화 신호 전송
            self.target_product_pub.publish(String(data=target_barcode)) # 목표 바코드 정보 전송
            self.ai_wait_start_time = self.get_clock().now()

            # 이전에 설정된 타이머가 있다면 제거
            if hasattr(self, '_delay_timer') and self._delay_timer:
                self.destroy_timer(self._delay_timer)
                self._delay_timer = None

            # AI 인식을 최대 8초까지 기다리는 폴링 타이머 가동
            self._delay_timer = self.create_timer(0.5, self.check_ai_result_and_proceed)
        elif status == GoalStatus.STATUS_ABORTED:
            # 목표 재전송(Preemption)이나 일시적인 경로 문제인 경우 즉시 보내지 않고 3초 쿨다운 적용
            if not self._is_handling_retry:
                self.get_logger().warn(f'Navigation was ABORTED (code: {status}). Waiting 3s for stabilization...')
                if self.retry_timer: self.destroy_timer(self.retry_timer)
                self.retry_timer = self.create_timer(3.0, self._trigger_retry)
            
            # 만약 일시정지 상태도 아니고 주행이 완전히 멈춘 것이 확실할 때만 에러 처리
            if not self.is_paused:
                self.publish_status('nav_alert')
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn(f'Navigation was CANCELED (code: {status}). Waiting for next action.')
            # 취소 시에는 순찰을 완전히 끄지 않고 유지합니다. (장애물 회피 등에서 발생 가능)
        else:
            self.get_logger().error(f'[상태 변경] Navigation FAILED (code: {status}). 안전을 위해 순찰을 중단합니다.')
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
        """정해진 주기마다 서버로 현재 위치 및 상태 보고 (Non-blocking Thread 방식)"""
        # 위치 정보가 아직 없더라도 프로세스 생존 신호를 위해 보고를 수행합니다.
        # (비활성 상태일 경우 0.0, 0.0 으로 보고됨)
        if not self.pose_received:
             self.get_logger().warn('Waiting for AMCL pose, reporting heartbeat only...')

        # 상태 결정 로직
        status = "IDLE"
        if self.is_patrolling:
            status = "SCANNING" if self.is_waiting_for_ai else "PATROLLING"

        # 메인 스레드 블로킹 방지를 위해 별도 스레드에서 DB 보고 수행
        threading.Thread(
            target=self.db.report_robot_pose,
            args=(self.current_x, self.current_y, status),
            daemon=True
        ).start()

        # UI 인터페이스(patrol_interface.py)를 위한 지속 발행
        status_for_ui = "patrolling" if self.is_patrolling else "idle"
        self.publish_status(status_for_ui)

    def ai_callback(self, msg):
        """PC로부터 검증 상세 데이터를 수신"""
        if self.is_waiting_for_ai and len(msg.detections) > 0:
            res = msg.detections[0]
            # 수신된 데이터를 내부 변수에 저장
            self.latest_ai_data = {
                "class_id": res.class_id,
                "detected_barcode": res.detected_barcode,
                "confidence": res.confidence,
                "status": res.status
            }

    def battery_callback(self, msg):
        """로봇의 배터리 상태를 수신하여 저장 (0.0~1.0 또는 0.0~100.0 대응)"""
        val = float(msg.percentage)

        # NaN 또는 Inf 값이 들어오면 무시 (통신 초기화 전 등 방어 로직)
        if math.isnan(val) or math.isinf(val):
            return

        # 1.0 이하면 표준 규격(0.0~1.0)으로 보고 100을 곱함, 그 이상이면 이미 퍼센트(0~100)임
        self.current_battery = val * 100.0 if val <= 1.0 else val

    def report_battery_to_server(self):
        """서버로 배터리 상태 보고 (Non-blocking Thread 방식)"""
        def run_report():
            success = self.db.report_battery(self.current_battery)
            if not success:
                self.get_logger().warn("Failed to report battery status to server.")

        threading.Thread(target=run_report, daemon=True).start()

    def check_ai_result_and_proceed(self):
        """결과가 왔는지 확인하고 DB에 기록"""
        if not self.is_waiting_for_ai: return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        target_barcode = self.shelves[shelf_name].get('tag_barcode', 'UNKNOWN')

        elapsed = (self.get_clock().now() - self.ai_wait_start_time).nanoseconds / 1e9

        # [수정] 단순히 데이터가 있는지가 아니라, '정상' 결과를 얻었거나 시간이 다 됐을 때만 종료
        has_success = hasattr(self, 'latest_ai_data') and self.latest_ai_data and self.latest_ai_data.get('status') == '정상'
        
        if has_success or elapsed > self.ai_wait_timeout:
            self.is_waiting_for_ai = False
            self.ai_mode_pub.publish(Bool(data=False)) # PC 연산 종료 요청

            if self._delay_timer:
                self.destroy_timer(self._delay_timer)

            # 데이터가 없을 경우(타임아웃)를 대비한 기본값 설정
            data = getattr(self, 'latest_ai_data', None) or {
                "class_id": -1, "detected_barcode": "TIMEOUT", "confidence": 0.0, "status": "Fail"
            }

            # 요구하신 형식대로 self.last_detection 구성
            self.last_detection = {
                "tag_barcode": target_barcode,         # 원래 있어야 할 바코드
                "detected_barcode": data["detected_barcode"], # 실제로 인식된 바코드
                "yolo_class_id": data["class_id"],     # 물체 클래스 번호
                "confidence": data["confidence"]       # 신뢰도
            }

            # DB에 최종 리포트
            if target_barcode not in self.reported_tags:
                self.db.report_detection(
                    tag_barcode=self.last_detection["tag_barcode"],
                    patrol_id=self.current_patrol_id or 0,
                    waypoint_id=self.shelves[shelf_name].get('waypoint_id', 1),
                    x=self.current_x,
                    y=self.current_y,
                    detected_barcode=self.last_detection["detected_barcode"],
                    yolo_class_id=self.last_detection["yolo_class_id"],
                    confidence=self.last_detection["confidence"]
                )
                self.reported_tags.add(target_barcode)
                self.get_logger().info(f"DB 저장 완료: {target_barcode} - {data['status']}")

            # 다음 위치로 이동
            self.latest_ai_data = None # 데이터 초기화
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


def main(args=None):
    rclpy.init(args=args)
    node = PatrolNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
