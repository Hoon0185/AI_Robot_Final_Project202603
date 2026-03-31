def sync_callback(self, img_msg, det_msg):
    frame = self.bridge.compressed_imgmsg_to_cv2(img_msg)
