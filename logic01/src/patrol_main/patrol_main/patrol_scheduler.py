import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time

class PatrolScheduler(Node):
    def __init__(self):
        super().__init__('patrol_scheduler')
        
        # 1. 파라미터 선언 (기본값 60분 = 3600초)
        self.declare_parameter('patrol_interval_min', 60.0)
        self.update_interval()
        
        self.publisher_ = self.create_publisher(String, 'patrol_cmd', 10)
        
        # 2. 1초마다 시계를 체크하는 타이머 실행
        self.timer = self.create_timer(1.0, self.clock_check_callback)
        
        # 3. 파라미터 변경 콜백
        self.add_on_set_parameters_callback(self.parameter_callback)
        
        self.last_triggered_time = -1
        self.get_logger().info(f'Patrol Scheduler Node started. Default interval: {self.interval_min} min (Aligned to clock)')

    def update_interval(self):
        self.interval_min = self.get_parameter('patrol_interval_min').get_parameter_value().double_value
        self.interval_sec = self.interval_min * 60.0

    def parameter_callback(self, params):
        for param in params:
            if param.name == 'patrol_interval_min':
                if param.value > 0:
                    self.update_interval()
                    self.get_logger().info(f'Patrol interval updated to: {self.interval_min} min')
                    return rclpy.node.SetParametersResult(successful=True)
                else:
                    return rclpy.node.SetParametersResult(successful=False)
        return rclpy.node.SetParametersResult(successful=True)

    def clock_check_callback(self):
        # 현재 에포크 시간(초)을 가져옴
        current_time = time.time()
        current_timestamp = int(current_time)
        
        # 주기(초)에 맞춰 정렬된 시간인지 확인 (예: 3600초 주기면 3600의 배수일 때)
        # last_triggered_time을 체크하여 한 초에 여러 번 실행되는 것을 방지
        if current_timestamp % int(self.interval_sec) == 0:
            if current_timestamp != self.last_triggered_time:
                self.trigger_patrol()
                self.last_triggered_time = current_timestamp

    def trigger_patrol(self):
        msg = String()
        msg.data = 'START_PATROL'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Clock aligned trigger: Starting Patrol at {time.strftime("%H:%M:%S", time.localtime())}')

def main(args=None):
    rclpy.init(args=args)
    import time
    patrol_scheduler = PatrolScheduler()
    rclpy.spin(patrol_scheduler)
    patrol_scheduler.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
