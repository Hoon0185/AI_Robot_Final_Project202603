import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from protect_product_msgs.msg import DetectionArray
from cv_bridge import CvBridge
from ultralytics import YOLO

class Detector(Node):
    def __init__(self):
        super().__init__('detector')
        self.model = YOLO("/home/bird99/AI_Robot_Final_Project202603/src/protect_product/models/products.pt")
        self.bridge = CvBridge()
        self.publisher = self.create_publisher(DetectionArray, '/det_objs', 10)
        self.subscription = self.create_subscription(CompressedImage, '/image_raw/compressed', self.callback, 10)

    def callback(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg)
        results = self.model(frame)

        det_msg = DetectionArray()
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            det_msg.x1.append(x1)
            det_msg.y1.append(y1)
            det_msg.x2.append(x2)
            det_msg.y2.append(y2)
            det_msg.class_ids.append(int(box.cls[0]))
        self.publisher.publish(det_msg)
