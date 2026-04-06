import rclpy
from rclpy.node import Node
from protect_product_msgs.msg import DetectionArray
import os

class ViewerNode(Node):
    def __init__(self):
        super().__init__('viewer_node')
        self.qr_val = "None_QR"
        self.sub = self.create_subscription(DetectionArray, '/verified_objs', self.callback, 10)

    def callback(self, msg):
        print("\033[H\033[J", end="") # 화면 청소 최적화
        for i in range(len(msg.class_ids)):
            if msg.class_ids[i] == 999:
                val = msg.class_names[i]
                if val not in ["None_QR", "Scanning..."]: self.qr_val = val

        print("="*50)
        print(f"       [ 실시간 편의점 재고 검출 현황 ]")
        print("="*50)
        print(f" [최근 인식된 QR]: {self.qr_val}") # 상시 노출
        print("-" * 50)
        print(f" {'TYPE':<10} | {'NAME':<15} | {'ID':<5} | {'CONF':<7}")
        print("="*50)

        for i in range(len(msg.class_ids)):
            if msg.class_ids[i] != 999:
                name = msg.class_names[i]
                prod_id = msg.class_ids[i] + 1
                # 신뢰도(Score) 가져오기
                score_str = "N/A"
                if hasattr(msg, 'scores') and len(msg.scores) > i:
                    score_str = f"{msg.scores[i]*100:.1f}%"
                print(f" [PRODUCT] | {name:<15} | {prod_id:<5} | {score_str:<7}")
        print("="*50)

def main(args=None):
    rclpy.init(args=args)
    node = ViewerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
