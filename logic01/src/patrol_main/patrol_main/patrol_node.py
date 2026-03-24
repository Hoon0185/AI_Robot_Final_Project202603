import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import yaml
import os
from ament_index_python.packages import get_package_share_directory

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')
        
        # 1. Nav2 Action Client 설정
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # 2. 좌표 데이터 로드
        self.load_shelves()
        
        # 3. 순찰 상태 관리
        self.shelf_list = list(self.shelves.keys())
        self.current_shelf_idx = 0
        self.is_patrolling = False
        
        # 4. 순찰 명령 구독
        self.cmd_sub = self.create_subscription(String, 'patrol_cmd', self.cmd_callback, 10)
        
        self.get_logger().info('Patrol Main Node has been started.')

    def load_shelves(self):
        # 패키지 공유 디렉토리에서 yaml 파일을 읽어옵니다.
        pkg_dir = get_package_share_directory('patrol_main')
        yaml_path = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            self.shelves = config['shelves']

    def cmd_callback(self, msg):
        if msg.data == 'START_PATROL' and not self.is_patrolling:
            self.get_logger().info('Starting Patrol Sequence...')
            self.is_patrolling = True
            self.current_shelf_idx = 0
            self.send_next_goal()

    def send_next_goal(self):
        if self.current_shelf_idx >= len(self.shelf_list):
            self.get_logger().info('Patrol Completed!')
            self.is_patrolling = False
            return

        shelf_name = self.shelf_list[self.current_shelf_idx]
        coords = self.shelves[shelf_name]
        
        self.get_logger().info(f'Navigating to {shelf_name}...')
        
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
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
        result = future.result().result
        self.get_logger().info(f'Arrival at shelf {self.shelf_list[self.current_shelf_idx]} confirmed.')
        
        # 여기서 영상 인식을 위한 대기 로직 등을 추가할 수 있습니다.
        time.sleep(2) 
        
        self.current_shelf_idx += 1
        self.send_next_goal()

def main(args=None):
    rclpy.init(args=args)
    import time # Result callback에서 사용
    node = PatrolNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
