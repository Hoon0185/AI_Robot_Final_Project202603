import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray
import yaml
import os
from ament_index_python.packages import get_package_share_directory

class PatrolVisualizer(Node):
    def __init__(self):
        super().__init__('patrol_visualizer')
        
        self.declare_parameter('map_frame', 'map')
        self.map_frame = self.get_parameter('map_frame').get_parameter_value().string_value
        
        self.publisher = self.create_publisher(MarkerArray, 'shelf_markers', 10)
        self.load_shelves()
        
        self.timer = self.create_timer(1.0, self.publish_markers)
        self.get_logger().info('Patrol Visualizer Node started.')

    def load_shelves(self):
        pkg_dir = get_package_share_directory('patrol_main')
        yaml_path = os.path.join(pkg_dir, 'config', 'shelf_coords.yaml')
        try:
            with open(yaml_path, 'r') as f:
                config = yaml.safe_load(f)
                if '/**' in config:
                    self.shelves = config['/**']['ros__parameters']['shelves']
                elif 'patrol_node' in config:
                    self.shelves = config['patrol_node']['ros__parameters']['shelves']
                else:
                    self.shelves = config['shelves']
        except Exception as e:
            self.get_logger().error(f'Failed to load shelves: {e}')
            self.shelves = {}

    def publish_markers(self):
        if not self.shelves:
            return
            
        marker_array = MarkerArray()
        
        for i, (name, coords) in enumerate(self.shelves.items()):
            # 1. Sphere Marker for Location
            sphere = Marker()
            sphere.header.frame_id = self.map_frame
            sphere.header.stamp = self.get_clock().now().to_msg()
            sphere.ns = "shelves"
            sphere.id = i
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = float(coords['x'])
            sphere.pose.position.y = float(coords['y'])
            sphere.pose.position.z = 0.1
            sphere.scale.x = 0.2
            sphere.scale.y = 0.2
            sphere.scale.z = 0.2
            sphere.color.a = 0.8
            sphere.color.r = 0.0
            sphere.color.g = 1.0
            sphere.color.b = 0.0
            marker_array.markers.append(sphere)
            
            # 2. Text Marker for Label
            text = Marker()
            text.header.frame_id = self.map_frame
            text.header.stamp = self.get_clock().now().to_msg()
            text.ns = "labels"
            text.id = i + 100
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose.position.x = float(coords['x'])
            text.pose.position.y = float(coords['y'])
            text.pose.position.z = 0.4
            text.scale.z = 0.15 # Text height
            text.color.a = 1.0
            text.color.r = 1.0
            text.color.g = 1.0
            text.color.b = 1.0
            text.text = name
            marker_array.markers.append(text)
            
        self.publisher.publish(marker_array)

def main(args=None):
    rclpy.init(args=args)
    node = PatrolVisualizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
