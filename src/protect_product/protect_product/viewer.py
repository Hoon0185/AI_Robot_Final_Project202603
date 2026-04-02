import rclpy
from rclpy.node import Node
from protect_product_msgs.msg import DetectionArray
import os

class DataDashboardNode(Node):
    def __init__(self):
        super().__init__('data_dashboard_node')
        qr_val = "인식된 QR이 없습니다"
        self.subscription = self.create_subscription(
            DetectionArray,
            '/verified_objs',  # Verifier가 준 데이터 토픽
            self.data_callback,
            10)
        self.get_logger().info('데이터 대시보드: 실시간 검출 현황 출력')

    def data_callback(self, msg):
        # 터미널 화면 청소 (실시간 갱신 효과)
        os.system('clear')
        for i in range(len(msg.class_ids)):
            if msg.class_ids[i] == 999:
                qr_val = msg.class_names[i]

        print("="*50)
        print(f"       [ 실시간 편의점 재고 검출 현황 ]")
        print("="*50)
        print(f" [최근 인식된 QR]: {qr_val}") # 상시 노출
        print("-" * 50)

        if not msg.class_ids:
            print("현재 확인되는 물품은 없습니다")
        else:
            # 검출된 물체들을 루프 돌며 출력
            for i in range(len(msg.class_ids)):
                name = msg.class_names[i]
                c_id = msg.class_ids[i]

                # QR 데이터(999)와 일반 물체 구분
                if c_id == 999:
                    print(f"[QR LABEL] 데이터: {name}")
                else:
                    print(f"[PRODUCT ] 이름: {name:<15} (ID: {c_id+1})")

        print("="*50)
        print("Tip: 이미지는 Verifier 창에서 확인하세요.")

def main(args=None):
    rclpy.init(args=args)
    node = DataDashboardNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
