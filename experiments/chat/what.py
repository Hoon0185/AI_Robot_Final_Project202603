import os
import cv2
import time
from google import genai
import mysql.connector
from dotenv import load_dotenv

# Load .env for database config (if exists)
load_dotenv()

# Gemini API Configuration
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Warning: GEMINI_API_KEY not found in environment.")
    client = None
else:
    client = genai.Client(api_key=api_key)

# Database Connection Config
DB_CONFIG = {
    'host': os.getenv('LOCAL_DB_HOST', 'localhost'),
    'user': os.getenv('LOCAL_DB_USER', 'gilbot'),
    'password': os.getenv('LOCAL_DB_PASSWORD', 'robot123'),
    'database': os.getenv('LOCAL_DB_NAME', 'gilbot')
}

def capture_image(filename="capture.jpg"):
    """Shows a live camera preview and captures an image when the spacebar is pressed."""
    print("Initializing camera preview...")
    print("Commands: [Space]: Capture, [q] or [Esc]: Quit")
    
    cap = None
    for index in [0, 1, 2]:
        temp_cap = cv2.VideoCapture(index)
        if temp_cap.isOpened():
            ret, _ = temp_cap.read()
            if ret:
                cap = temp_cap
                print(f"Connected to camera index: {index}")
                break
            temp_cap.release()

    if cap is None:
        print("Error: Could not open any camera device.")
        return None
    
    window_name = "Camera Preview - Press Space to Capture"
    captured_file = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to grab frame.")
                break

            # Show the frame
            cv2.imshow(window_name, frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            # [Space] key to capture
            if key == ord(' '):
                cv2.imwrite(filename, frame)
                print(f"Image captured and saved to {filename}")
                captured_file = filename
                break
            
            # [q] or [Esc] key to quit
            elif key == ord('q') or key == 27:
                print("Capture cancelled by user.")
                break
                
    finally:
        cap.release()
        cv2.destroyAllWindows()
        # Briefly wait for windows to close properly
        cv2.waitKey(1)

    return captured_file

def identify_product_from_image(image_path):
    """Uploads image to Gemini and returns the recognized product name."""
    if not client:
        return "None"

    print("Processing image with Gemini (v2.5 Flash)...")

    # Load the image
    with open(image_path, "rb") as f:
        image_data = f.read()

    # Prompt Gemini to extract the product name
    prompt = "이 사진 속에 정면으로 보이는 상품이 무엇인지 한국어로 상품명만 딱 한 단어로 말해줘. 만약 상품명을 찾을 수 없다면 'None'이라고 답변해줘."

    # Use the multimodal capabilities of gemini-2.5-flash
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
        ]
    )

    product_name = response.text.strip()
    print(f"Recognized Product: {product_name}")
    return product_name

def get_product_info(product_name):
    """Searches the database for detailed product information."""
    if not product_name or product_name.lower() == "none":
        return "상품을 인식하지 못했습니다."

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT pm.product_name, pm.category, pm.current_inventory_qty, w.waypoint_name
        FROM product_master pm
        LEFT JOIN waypoint_product_plan wpp ON pm.product_id = wpp.product_id
        LEFT JOIN waypoint w ON wpp.waypoint_id = w.waypoint_id
        WHERE pm.product_name LIKE %s;
        """
        search_term = f"%{product_name}%"
        cursor.execute(query, (search_term,))
        result = cursor.fetchone()

        if result:
            info = f"인식된 상품: '{result['product_name']}'\n"
            info += f"- 카테고리: {result['category']}\n"
            info += f"- 현재 재고: {result['current_inventory_qty']}개\n"
            info += f"- 위치: {result['waypoint_name'] if result['waypoint_name'] else '정보 없음'}"
            return info
        else:
            return f"'{product_name}' 제품을 인식했으나, 데이터베이스에서 상응하는 정보를 찾을 수 없습니다."

    except mysql.connector.Error as err:
        return f"데이터베이스 오류: {err}"
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    try:
        img_file = "capture.jpg"
        if capture_image(img_file):
            product_name = identify_product_from_image(img_file)

            info = get_product_info(product_name)
            print(f"\n--- [인식 결과] ---\n{info}\n-------------------")

            # Keep the image for review? No, delete it if it's temporary.
            # os.remove(img_file)
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
