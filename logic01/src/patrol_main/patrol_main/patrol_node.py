import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from action_msgs.msg import GoalStatus
import yaml
import os
import time
import json
from datetime import datetime
from ament_index_python.packages import get_package_share_directory

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')

        # 1. Nav2 Action Client 설정
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # 2. 파라미터 및 프레임 설정
        # 네임스페이스가 있으면 'NS/map', 없으면 'map'을 기본으로 사용
        ns = self.get_namespace().strip('/')
        default_frame = f'{ns}/map' if ns else 'map'
        self.declare_parameter('map_frame', default_frame)
        self.map_frame = self.get_parameter('map_frame').get_parameter_value().string_value
        self.load_shelves()

        # 3. 순찰 상태 관리
        self.shelf_list = list(self.shelves.keys())
        self.current_shelf_idx = 0
        self.is_patrolling = False

        # 4. 순찰 명령 구독
        self.cmd_sub = self.create_subscription(String, 'patrol_cmd', self.cmd_callback, 10)

        # 5. 순찰 상태 발행 (UI용)
        self.patrol_status_pub = self.create_publisher(String, 'patrol_status', 10)
        self.start_time = None
        self.end_time = None

        self.get_logger().info('Patrol Main Node has been started.')

    def load_shelves(self):
        # 패키지 공유 디렉토리에서 yaml 파일을 읽어옵니다.
        pkg_dir = get_package_share_directory('patrol_main')
        yaml_path = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            # ROS 2 파라미터 형식 (/** -> ros__parameters -> shelves)에 맞춰 읽어옵니다.
            if '/**' in config:
                self.shelves = config['/**']['ros__parameters']['shelves']
            elif 'patrol_node' in config:
                self.shelves = config['patrol_node']['ros__parameters']['shelves']
            else:
                self.shelves = config['shelves']

    def cmd_callback(self, msg):
        if msg.data == 'START_PATROL' and not self.is_patrolling:
            self.get_logger().info('Starting Patrol Sequence...')
            self.is_patrolling = True
            self.start_time = datetime.now()
            self.current_shelf_idx = 0
            self.publish_status('patrolling')
            self.send_next_goal()

    def send_next_goal(self):
        if self.current_shelf_idx >= len(self.shelf_list):
            self.get_logger().info('Patrol Completed!')
            self.is_patrolling = False
            self.end_time = datetime.now()
            self.publish_status('completed')
            return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]


        self.get_logger().info(f'Navigating to {shelf_name} (x: {coords["x"]}, y: {coords["y"]})...')

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = self.map_frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = float(coords['x'])
        goal_msg.pose.pose.position.y = float(coords['y'])

        # Orientation (Simplified: yaw to quaternion)
        import math
        yaw = float(coords['yaw'])
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self._action_client.wait_for_server()
        self._send_goal_future = self._action_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected :(')
            self.is_patrolling = False
            return

        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'Arrival at shelf {self.shelf_list[self.current_shelf_idx]} confirmed.')

            # 2초 뒤에 proceed_to_next_shelf 함수가 실행됩니다.
            self._delay_timer = self.create_timer(2.0, self.proceed_to_next_shelf)
        else:
            # 실패 시 순찰을 종료하지 않고 다음 선반으로 넘어감
            self.get_logger().warn(f'Failed to reach {self.shelf_list[self.current_shelf_idx]}. Status: {status}')
            self.get_logger().info('Skipping to the next shelf...')
            self.current_shelf_idx += 1
            if self.is_patrolling:
                self.publish_status('patrolling')
            self.send_next_goal()

    def proceed_to_next_shelf(self):
        # 1회성 지연을 위한 타이머이므로 실행 직후 취소(cancel) 해줍니다.
        if self._delay_timer:
            self._delay_timer.cancel()

        self.current_shelf_idx += 1
        if self.is_patrolling:
            self.publish_status('patrolling')
        self.send_next_goal()

    def publish_status(self, status):
        info = {
            'status': status,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if status == 'patrolling':
            info['start_time'] = self.start_time.strftime('%Y-%m-%d %H:%M:%S')
            if self.current_shelf_idx < len(self.shelf_list):
                info['current_shelf'] = self.shelf_list[self.current_shelf_idx]
                info['progress'] = f"{self.current_shelf_idx + 1}/{len(self.shelf_list)}"
        elif status == 'completed':
            info['start_time'] = self.start_time.strftime('%Y-%m-%d %H:%M:%S')
            info['end_time'] = self.end_time.strftime('%Y-%m-%d %H:%M:%S')
            duration = self.end_time - self.start_time
            # Format duration as HH:MM:SS
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            info['duration'] = f"{hours:02}:{minutes:02}:{seconds:02}"
            info['total_shelves'] = len(self.shelf_list)
        
        msg = String()
        msg.data = json.dumps(info, ensure_ascii=False)
        self.patrol_status_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = PatrolNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
