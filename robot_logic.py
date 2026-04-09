import sys
import os
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage
from PyQt6.QtCore import pyqtSignal, QObject

# ROS 2 패키지 경로 추가 (logic01/src/patrol_main 하위의 모듈을 참조하기 위함)
current_dir = os.path.dirname(os.path.abspath(__file__))
patrol_main_path = os.path.join(current_dir, 'logic01', 'src', 'patrol_main')
if patrol_main_path not in sys.path:
    sys.path.append(patrol_main_path)

try:
    from patrol_main.patrol_interface import PatrolInterface
    from patrol_main.obstacle_interface import ObstacleInterface
except ImportError:
    # 패키지 구조에 따라 직접 참조가 필요한 경우 하드코딩된 경로 추가
    sys.path.append(os.path.join(patrol_main_path, 'patrol_main'))
    try:
        from patrol_interface import PatrolInterface
        from obstacle_interface import ObstacleInterface
    except ImportError:
        # 디버그 모드를 위해 임포트 실패 시 pass 처리 (is_debug에서 걸러짐)
        PatrolInterface = None
        ObstacleInterface = None

try:
    import rclpy
except ImportError:
    rclpy = None

class LogicSignals(QObject):
    rtspFrameReceived = pyqtSignal(bytes)

class RobotLogicHandler:
    def __init__(self, ui_instance, debug_mode=False):
        self.ui = ui_instance
        self.is_debug = debug_mode # 디버그 모드 상태 저장
        self.cam_node = None
        # ROS 2 인터페이스 초기화 (디버그 모드가 아닐 때만 시도)
        self.ros_interface = None
        self.obstacle_manager = None
        self.rclpy = rclpy
        self._prepare_paths() #경로 설정 (로직 핸들러 생성 시점에 수행)
        if not self.is_debug:
            self._initialize_ros_nodes()
            try:
                if PatrolInterface:
                    self.ros_interface = PatrolInterface()
                else:
                    raise ImportError("PatrolInterface module not found.")
                if ObstacleInterface:
                    self.obstacle_manager = ObstacleInterface()
                    self.sub_obstacle_ui = self.ros_interface.node.create_subscription( String, 'obstacle_ui_log', self._obstacle_ui_callback, 10)
                else:
                    raise ImportError("ObstacleInterface module not found.")
            except Exception as e:
                self._log(f"[ERROR] ROS 2 Interface failed to start: {e}")
                self._log("[SYSTEM] 릴리즈 모드에서 연결 실패. 하드웨어를 확인하세요.")
        else:
            self._log("[SYSTEM] DEBUG MODE 활성화: 외부 연결(ROS/DB) 없이 시뮬레이션 데이터를 사용합니다.")

        self.signals = LogicSignals() # UI 이미지 전송용 시그널 객체

        self._setup_connections()
        self.current_patrol_min = 60
        self.current_obstacle_sec = 5
        self._load_initial_data()

        # UI 업데이트용 타이머 (ROS 상태 반영)
        from PyQt6.QtCore import QTimer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.sync_ros_status)
        self.status_timer.start(50) # 1초마다 동기화

    def _log(self, message):
        """터미널 출력(print)과 UI 콘솔(append_log)에 동시에 메시지를 남깁니다."""
        print(message)
        if hasattr(self.ui, 'append_log'):
            self.ui.append_log(message)

    def _obstacle_ui_callback(self, msg):
        """장애물 노드에서 보낸 문장(msg.data)를 UI로 바로 토스합니다."""
        self._log(msg.data)

    def _setup_connections(self):
        """
        UI(robot_ui.py)에서 정의된 시그널들을 실제 로직 함수에 연결합니다.
        UI 코드를 직접 수정하지 않고도 여기서 모든 제어가 가능합니다.
        """
        # 설정 관련
        self.ui.patrolTimeConfirmed.connect(self.on_patrol_set)
        self.ui.obstacleConfirmed.connect(self.on_obstacle_set)

        # 수동 제어 관련
        self.ui.moveCommand.connect(self.on_move_command)
        self.ui.buzzerClicked.connect(self.on_buzzer)
        self.ui.returnClicked.connect(self.on_return_patrol)
        self.ui.emergencyClicked.connect(self.on_emergency)
        self.ui.resetConfirmed.connect(self.on_reset_confirmed)

        # --- 추가: 수동 순찰 명령 시그널 연결 ---
        self.ui.patrolConfirmed.connect(self.on_patrol_confirmed)

        # DB 및 알림 갱신 요청
        self.ui.dbRefreshRequested.connect(self.update_inventory_db)
        self.ui.alarmRefreshRequested.connect(self.update_alarm_list)

        # 카메라 프레임 수신 (백엔드 -> UI)
        self.signals.rtspFrameReceived.connect(self.ui.display_compressed_image)

    def _prepare_paths(self):
        """복잡한 디렉토리 구조에 맞춰 sys.path를 정확히 설정합니다."""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 구조: logic01/logic01/src/protect_product/protect_product/camera.py
        # 'protect_product' 패키지를 포함하는 상위 폴더인 'src' 레벨을 경로에 넣어야 함
        ai_src_base = os.path.join(current_dir, 'logic01', 'logic01', 'src', 'protect_product')

        if ai_src_base not in sys.path:
            sys.path.append(ai_src_base)

        # PatrolInterface 경로 (logic01/src/patrol_main 대응)
        patrol_path = os.path.join(current_dir, 'logic01', 'src', 'patrol_main')
        if patrol_path not in sys.path:
            sys.path.append(patrol_path)

    def _initialize_ros_nodes(self):
        """실제 모듈을 임포트하고 노드 객체를 생성합니다."""
        import rclpy
        global IntegratedPCNode

        if self.rclpy is None:
            try:
                import rclpy
                self.rclpy = rclpy
            except:
                self._log("❌ rclpy 임포트 불가")
                return

        if not self.rclpy.ok():
            self.rclpy.init()

        # [A] AI 노드 임포트 및 생성
        try:
            from protect_product.camera import IntegratedPCNode
            self._log("✅ [SYSTEM] AI 인식 모듈 로드 성공")
        except ImportError as e:
            # 구조가 다를 경우를 대비한 2차 시도
            try:
                from camera import IntegratedPCNode
                self._log("✅ [SYSTEM] AI 모듈 로드 성공 (직접 참조)")
            except:
                self._log(f"❌ [SYSTEM] AI 모듈 임포트 최종 실패: {e}")
                IntegratedPCNode = None

        # [A-2] RTSP 마스터 스트리밍 노드 임포트 및 생성 (지연 해갈의 핵심)
        try:
            from protect_product.camera_node import RtspBridgeNode
            self.stream_node = RtspBridgeNode()
            self._log("🎥 [SYSTEM] RTSP 마스터 스트리밍 노드 활성화")
        except Exception as e:
            self._log(f"⚠️ [SYSTEM] 스트리밍 노드 생성 실패: {e}")
            self.stream_node = None

        try:
            if IntegratedPCNode:
                self.cam_node = IntegratedPCNode()
                self._log("🚀 [SYSTEM] AI 인식 노드 활성화 완료")

            if self.ros_interface and hasattr(self.ros_interface, 'get_name'):
                self.ros_interface = self.ros_interface # Placeholder

            # [C] 캠 지연 해결을 위한 ROS 이미지 구독 (RTSP 직접 연결 대신 사용)
            self.sub_image = self.ros_interface.node.create_subscription(
                CompressedImage, '/rtsp_image', self._image_callback, 10)
            self._log("📸 [SYSTEM] 캠 스트리밍 구독 시작 (/rtsp_image)")

        except Exception as e:
            self._log(f"⚠️ [SYSTEM] 노드 생성 중 오류 발생: {e}")

    def _image_callback(self, msg):
        """백엔드에서 오는 최적화된 이미지를 UI 시그널로 전달"""
        self.signals.rtspFrameReceived.emit(msg.data)

    def sync_ros_status(self):
        """ROS 노드를 1스텝씩 실행하고 UI를 갱신합니다."""
        if self.is_debug:
            self.ui.set_last_patrol_time("2026-03-31 16:30 (DEBUG MODE ACTIVE)")
            return

        # rclpy.spin_once를 통해 노드들의 콜백(카메라 추론 등)을 실제로 실행
        if rclpy.ok():
            if self.cam_node:
                rclpy.spin_once(self.cam_node, timeout_sec=0)

            if self.stream_node:
                rclpy.spin_once(self.stream_node, timeout_sec=0)

            if self.ros_interface and hasattr(self.ros_interface, 'get_name'):
                rclpy.spin_once(self.ros_interface, timeout_sec=0)

        # UI 갱신 로직 (주행 상태 표시)
        if not self.ros_interface: return
        status = self.ros_interface.get_recent_patrol_time()
        if status:
            # 1. 마지막 순찰 시간 및 상태 표시 (상세 정보 포함)
            time_info = status.get('start_time', 'No Data')
            s_type = status.get('status', 'IDLE')

            if s_type == 'patrolling':
                shelf = status.get('current_shelf', 'Moving...')
                progress = status.get('progress', '')
                display_text = f"{time_info} (순찰 중: {shelf} {progress})"
            else:
                display_text = f"{time_info} ({s_type})"

            # 로봇 온라인 여부에 따라 [OFFLINE] 표시 추가
            if not self.ros_interface.is_robot_online():
                display_text += " [OFFLINE]"

            self.ui.set_last_patrol_time(display_text)

            # 2. 미니맵 위치 실시간 업데이트 호출
            self.update_minimap_pose()

    def _load_initial_data(self):
        """앱 시작 시 초기 데이터를 DB에서 가져와 UI 및 ROS에 세팅"""
        self.update_inventory_db()
        self.update_alarm_list()

        # 서버에서 초기 설정값 가져와서 ROS 및 UI 동기화
        if self.ros_interface:
            config = self.ros_interface.get_db_config()
            if config:
                self._log(f"[LOGIC] 서버에서 초기 설정 로드: {config}")
                try:
                    # 1. 장애물 대기 시간 (UI 값 설정)
                    wait_time = config.get('avoidance_wait_time')
                    if wait_time is not None:
                        self.current_obstacle_sec = int(wait_time)
                        self.ui.obstacle_row['slider'].setValue(self.current_obstacle_sec)
                        if self.obstacle_manager:
                            self.obstacle_manager.set_wait_time(self.current_obstacle_sec)
                        self._log(f"[LOGIC] 서버 데이터로 장애물 대기시간 {self.current_obstacle_sec}초 동기화")

                    # 2. 순찰 간격 (UI 값 설정 및 ROS 파라미터 적용)
                    h = config.get('interval_hour', 0)
                    m = config.get('interval_minute', 0)
                    self.current_patrol_min = h * 60 + m
                    if self.current_patrol_min > 0:
                        self.ui.patrol_row['slider'].setValue(self.current_patrol_min)
                        self.ros_interface.set_patrol_interval(float(self.current_patrol_min))

                except Exception as e:
                    self._log(f"[ERROR] 초기 설정 반영 중 오류: {e}")
        elif self.is_debug:
            # 디버그 모드 시 기본 UI 초기값 설정
            self._log("[DEBUG] 초기 UI 데이터를 가상으로 세팅합니다.")
            self.ui.obstacle_row['slider'].setValue(10)
            self.ui.patrol_row['slider'].setValue(60)



        # 초기 상태 반영
        self.sync_ros_status()

    # --- [핸들러 함수들: 담당자들이 내용을 채울 부분] ---

    def on_patrol_set(self, val):
        """순찰 간격 설정 (상태 유지하며 DB 동기화)"""
        self.current_patrol_min = int(val)
        h, m = divmod(self.current_patrol_min, 60)
        self._log(f"[LOGIC] 순찰 간격 {val}분 설정 ({h}시간 {m}분)")

        if self.ros_interface:
            # 1. ROS 파라미터 업데이트
            self.ros_interface.set_patrol_interval(float(val))
            # 2. DB 서버 업데이트 (현재 장애물 대기 시간 유지)
            self.ros_interface.sync_config_to_db(
                avoidance_wait=self.current_obstacle_sec,
                hour=h,
                minute=m
            )
        elif self.is_debug:
            self._log(f"[DEBUG] DB 연결 없이 설정값 로컬 업데이트: {h}h {m}m")

    def on_obstacle_set(self, val):
        """장애물 대기 시간 설정 (상태 유지하며 DB 동기화)"""
        self.current_obstacle_sec = int(val)
        self._log(f"[LOGIC] 장애물 대기 시간 {val}초 설정 요청)")

        if self.obstacle_manager:
            success, msg = self.obstacle_manager.update_db_and_sync(val)
            self._log(f"[LOGIC] {msg}")
        elif self.is_debug:
            self._log(f"[DEBUG] DB 연결 없이 장애물 대기 시간 업데이트: {val}s")

    # 재고 알림
    def update_alarm_list(self):
        """재고 부족 물품 리스트 업데이트"""
        if self.ros_interface:
            data = self.ros_interface.get_alarm_data()
            self.ui.set_alarm_data(data)
        elif self.is_debug:
            # 디버그용 샘플 데이터
            debug_data = [("가상 상품A", "부족"), ("가상 상품B", "품절")]
            self.ui.set_alarm_data(debug_data)

    # DB 재고 조회
    def update_inventory_db(self):
        """DB에서 재고 데이터를 가져와 테이블에 뿌려줌"""
        if self.ros_interface:
            data = self.ros_interface.get_inventory_data()
            self.ui.set_db_data(data)
        elif self.is_debug:
            # 디버그용 샘플 데이터
            debug_data = [("1", "가상 상품A", "10", "A-1"), ("2", "가상 상품B", "0", "B-2")]
            self.ui.set_db_data(debug_data)

    # 수동 조작 패널 - 수동 조작
    def on_move_command(self, direction):
        if self.ros_interface:
            self._log(f"[LOGIC] 수동 이동: {direction}")
            self.ros_interface.move_robot(direction)
        elif self.is_debug:
            self._log(f"[DEBUG] 수동 이동: {direction}")

    # 수동 조작 패널 - 부저
    def on_buzzer(self):
        self._log("[LOGIC] 부저 작동 (3회 비프)")
        if self.ros_interface:
            self.ros_interface.beep_buzzer(3)
        elif self.is_debug:
            self._log("[DEBUG] 부저 작동 (3회 비프 시뮬레이션)")

    # 수동 조작 패널 - 복귀 명령
    def on_return_patrol(self):
        if self.ros_interface:
            self.ros_interface.return_to_base()
            self._log("[LOGIC] 복귀 명령 송출")
        elif self.is_debug:
            self._log("[DEBUG] 복귀 명령 송출")

    # 수동 조작 패널 - 비상 정지
    def on_emergency(self):
        self._log("[LOGIC] 비상 정지!")
        if self.ros_interface:
            self.ros_interface.trigger_emergency_stop()
        elif self.is_debug:
            self._log("[DEBUG] 비상 정지!")

    # 초기 위치 명령 패널 - 예 - 복귀
    # 기능은 수동 조작 패널의 복귀 명령과 같음
    def on_reset_confirmed(self):
        if self.ros_interface:
            self.ros_interface.reset_position()
            self._log("[LOGIC] 초기 위치로")
        elif self.is_debug:
            self._log("[DEBUG] 초기 위치로")

    # 수동 순찰 명령
    def on_patrol_confirmed(self):
        """수동 순찰 명령 팝업에서 '시작'을 클릭했을 때 호출"""
        if self.ros_interface:
            self.ros_interface.trigger_manual_patrol()
            self._log("[LOGIC] 수동 순찰 명령. 순찰 시작")
        elif self.is_debug:
            self._log("[DEBUG] 수동 순찰 명령. 순찰 시작")

    def update_minimap_pose(self):
        """서버/ROS에서 온 최신 좌표를 MinimapWidget(minimap.py)에 반영합니다."""
        if not hasattr(self.ui, 'minimap') or self.ui.minimap is None:
            return

        if self.is_debug:
            self.ui.minimap.set_robot_pose(0.0, 0.0)
            return

        if not self.ros_interface:
            return

        # 인터페이스로부터 최신 통합 상태 데이터 획득
        status = self.ros_interface.get_recent_patrol_time()

        # 데이터가 있고 좌표 정보(robot_x, robot_y)가 포함되어 있다면 미니맵 갱신
        if status and 'robot_x' in status and 'robot_y' in status:
            curr_x = float(status.get('robot_x', 0.0))
            curr_y = float(status.get('robot_y', 0.0))
            self.ui.minimap.set_robot_pose(curr_x, curr_y)
        else:
            # 좌표가 없는 경우에도 기본 맵은 계속 렌더링되도록 함
            self.ui.minimap.update_map_display()
