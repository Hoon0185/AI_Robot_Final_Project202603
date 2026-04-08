import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
import json
import time

class PatrolScheduler(Node):
    def __init__(self):
        super().__init__('patrol_scheduler')
        
        # 1. 파라미터 선언
        # 모드: 'periodic' (주기), 'scheduled' (특정 시간 목록)
        self.declare_parameter('patrol_mode', 'periodic')
        self.declare_parameter('patrol_interval_min', 60.0)
        self.declare_parameter('reference_time', '00:00') # 주기 시작 기준점 (HH:MM)
        self.declare_parameter('scheduled_times', ['09:00', '13:00', '18:00']) # 특정 시간 목록
        
        self.update_config()
        
        # 명령 발행 (절대 경로)
        self.publisher_ = self.create_publisher(String, '/patrol_cmd', 10)
        
        # [추가] 로봇의 현재 상태를 구독하여 순찰 중인지 확인
        self.status_sub = self.create_subscription(
            String, '/patrol_status', self._status_callback, 10)
        self.is_robot_busy = False # 로봇의 동작 여부 플래그
        
        # 2. 서비스 서버 추가 (UI 수동 트리거용)
        self.srv = self.create_service(Trigger, 'trigger_manual_patrol', self.manual_trigger_callback)
        
        self.timer = self.create_timer(1.0, self.clock_check_callback)
        self.add_on_set_parameters_callback(self.parameter_callback)
        
        self.last_triggered_time = -1
        self.get_logger().info('Patrol Scheduler Node enhanced. Ready for UI integration.')

    def _status_callback(self, msg):
        """로봇의 상태를 확인하여 순찰 중인지 여부를 업데이트합니다."""
        try:
            status_data = json.loads(msg.data)
            status = status_data.get("status", "").upper()
            # 순찰 중이거나 이동 중이면 Busy 상태로 판단
            if status in ["PATROLLING", "MOVE_TO_GOAL", "MOVING"]:
                self.is_robot_busy = True
            else:
                self.is_robot_busy = False
        except:
            # JSON 파싱 실패 시 보수적으로 접근 (Busy 아님으로 간주하거나 이전 상태 유지)
            pass

    def update_config(self, params=None):
        if params:
            for param in params:
                if param.name == 'patrol_mode':
                    self.mode = param.value
                elif param.name == 'patrol_interval_min':
                    self.interval_sec = float(param.value) * 60.0
                elif param.name == 'reference_time':
                    self.ref_time_str = param.value
                    try:
                        h, m = map(int, self.ref_time_str.split(':'))
                        self.ref_offset_sec = h * 3600 + m * 60
                    except:
                        self.ref_offset_sec = 0
                elif param.name == 'scheduled_times':
                    self.sched_times = param.value
        else:
            self.mode = self.get_parameter('patrol_mode').get_parameter_value().string_value
            self.interval_sec = self.get_parameter('patrol_interval_min').get_parameter_value().double_value * 60.0
            self.ref_time_str = self.get_parameter('reference_time').get_parameter_value().string_value
            self.sched_times = self.get_parameter('scheduled_times').get_parameter_value().string_array_value
            
            try:
                h, m = map(int, self.ref_time_str.split(':'))
                self.ref_offset_sec = h * 3600 + m * 60
            except:
                self.ref_offset_sec = 0
                self.get_logger().error('Invalid reference_time format. Use HH:MM')

    def parameter_callback(self, params):
        self.get_logger().info('Updating parameters dynamically...')
        self.update_config(params)
        return rclpy.node.SetParametersResult(successful=True)

    def clock_check_callback(self):
        now = time.localtime()
        current_time_str = time.strftime("%H:%M", now)
        current_timestamp = int(time.time())
        seconds_since_midnight = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec

        if self.mode == 'periodic':
            diff = seconds_since_midnight - self.ref_offset_sec
            if diff >= 0 and diff % int(self.interval_sec) == 0:
                if current_timestamp != self.last_triggered_time:
                    # [보완] 로봇이 한가할 때만 트리거
                    if not self.is_robot_busy:
                        self.trigger_patrol(f'Periodic mode ({self.ref_time_str} start)')
                    else:
                        self.get_logger().warn('Periodic trigger skipped: Robot is already busy.')
                    self.last_triggered_time = current_timestamp
        
        elif self.mode == 'scheduled':
            if current_time_str in self.sched_times and now.tm_sec == 0:
                if current_timestamp != self.last_triggered_time:
                    # [보완] 로봇이 한가할 때만 트리거
                    if not self.is_robot_busy:
                        self.trigger_patrol(f'Scheduled mode (Time: {current_time_str})')
                    else:
                        self.get_logger().warn(f'Scheduled trigger ({current_time_str}) skipped: Robot busy.')
                    self.last_triggered_time = current_timestamp

    def trigger_patrol(self, reason):
        msg = String()
        msg.data = 'START_PATROL'
        self.publisher_.publish(msg)
        self.get_logger().info(f'[{reason}] Starting Patrol at {time.strftime("%H:%M:%S", time.localtime())}')

    def manual_trigger_callback(self, request, response):
        # 수동 트리거는 사용자의 직접 명령이므로 Busy 여부와 상관없이 일단 명령을 보냅니다.
        self.get_logger().info('Manual patrol trigger received via Service.')
        self.trigger_patrol('Manual trigger via UI')
        response.success = True
        response.message = "Patrol started manually."
        return response

def main(args=None):
    rclpy.init(args=args)
    patrol_scheduler = PatrolScheduler()
    try:
        rclpy.spin(patrol_scheduler)
    except KeyboardInterrupt:
        pass
    finally:
        patrol_scheduler.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()