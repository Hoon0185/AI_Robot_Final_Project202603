import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
from rclpy.qos import QoSProfile, ReliabilityPolicy

class ViewerNode(Node):
    def __init__(self):
        super().__init__('viewer_node')
        self.bridge = CvBridge()

        # 터틀봇 환경에 최적화된 QoS 설정
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            depth=10
        )

        # Verifier가 보낸 최종 결과 이미지를 구독합니다.
        self.subscription = self.create_subscription(
            CompressedImage,
            '/verif_img/compressed',
            self.image_callback,
            qos_profile)

        self.get_logger().info('Viewer 노드 가동: 실시간 모니터링 창을 오픈합니다.')

    def image_callback(self, msg):
        try:
            # 압축된 ROS 이미지를 OpenCV 형식으로 변환
            frame = self.bridge.compressed_imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # 모니터링 창에 출력
            cv2.imshow("Mart Monitoring System", frame)

            # GUI 이벤트를 처리하기 위해 1ms 대기 (창이 닫히지 않게 함)
            cv2.waitKey(1)

        except Exception as e:
            self.get_logger().error(f'이미지 변환 중 오류 발생: {e}')

    def __del__(self):
        # 노드 종료 시 OpenCV 창을 닫습니다.
        cv2.destroyAllWindows()

def main(args=None):
    rclpy.init(args=args)
    node = ViewerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('사용자에 의해 노드가 종료되었습니다.')
    finally:
        # 종료 처리
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
