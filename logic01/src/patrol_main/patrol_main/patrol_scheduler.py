import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time

class PatrolScheduler(Node):
    def __init__(self):
        super().__init__('patrol_scheduler')
        
        # 1. 파라미터 선언 (기본값 60초)
        self.declare_parameter('patrol_interval', 60.0)
        self.interval = self.get_parameter('patrol_interval').get_parameter_value().double_value
        
        self.publisher_ = self.create_publisher(String, 'patrol_cmd', 10)
        
        # 2. 타이머 설정
        self.timer = self.create_timer(self.interval, self.timer_callback)
        
        # 3. 파라미터 변경 콜백 등록
        self.add_on_set_parameters_callback(self.parameter_callback)
        
        self.get_logger().info(f'Patrol Scheduler Node has been started. Current interval: {self.interval}s')

    def parameter_callback(self, params):
        for param in params:
            if param.name == 'patrol_interval' and param.type_ == rclpy.Parameter.Type.DOUBLE:
                new_interval = param.value
                if new_interval > 0:
                    self.interval = new_interval
                    # 기존 타이머를 취소하고 새로 생성하여 즉시 반영
                    self.timer.cancel()
                    self.timer = self.create_timer(self.interval, self.timer_callback)
                    self.get_logger().info(f'Patrol interval updated to: {self.interval}s')
                    return rclpy.node.SetParametersResult(successful=True)
                else:
                    self.get_logger().warn('Invalid interval value. Must be > 0.')
                    return rclpy.node.SetParametersResult(successful=False)
        return rclpy.node.SetParametersResult(successful=True)

    def timer_callback(self):
        msg = String()
        msg.data = 'START_PATROL'
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)

def main(args=None):
    rclpy.init(args=args)
    patrol_scheduler = PatrolScheduler()
    rclpy.spin(patrol_scheduler)
    patrol_scheduler.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
