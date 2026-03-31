import cv2
from cv_bridge import CvBridge

def image_callback(self, msg):
    frame = self.bridge.compressed_imgmsg_to_cv2(msg)
    cv2.imshow("Mart Monitoring System", frame)
    cv2.waitKey(1)
