"""
Đăng ký khuôn mặt bằng cách quay video 30 giây với khung hướng dẫn.
"""

import cv2
import os
import sys
import numpy as np
import shutil
import argparse
import time

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.recognition import Regconizer
from src.core.vectordb import VectorBD
from src.utils import check_is_id_exist

RECORD_SECONDS = 30

def main(name: str, id: int):
    os.makedirs('images', exist_ok=True)

    if check_is_id_exist(id):
        print(f"❌ ID {id} đã tồn tại trong database. Hãy chọn ID khác.")
        return

    # Tạo thư mục lưu ảnh
    dir_path = f'./images/{id}_{name}'
    os.makedirs(dir_path, exist_ok=True)

    # Khởi tạo nhận diện và DB
    rec = Regconizer()
    vt_db = VectorBD()

    # Mở camera
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("Lỗi: Không thể mở camera.")
        return

    def cleanup_and_exit(captured_anything=False):
        cam.release()
        cv2.destroyAllWindows()
        # Nếu thoát giữa chừng và chưa chụp được gì, xoá folder rỗng
        if not captured_anything and os.path.exists(dir_path):
            try:
                os.rmdir(dir_path) # rmdir chỉ xoá folder rỗng
            except OSError:
                pass # Folder không rỗng, không xoá
        print("Thoát chương trình đăng ký.")

    print(f"👉 Chuẩn bị quay trong {RECORD_SECONDS} giây...")
    print("👉 Hãy xoay mặt chậm rãi qua các góc (trái, phải, trên, dưới) trong khung hình bầu dục.")
    print("👉 Nhấn [Q] để thoát bất cứ lúc nào.")

    captured_frames = []
    start_time = time.time()

    while True:
        ret, frame = cam.read()
        if not ret:
            print("Không đọc được khung hình từ camera")
            break
        frame = cv2.flip(frame, 1)
        display_img = frame.copy()

        # Tính toán thời gian còn lại
        elapsed_time = time.time() - start_time
        remaining_time = max(0, RECORD_SECONDS - elapsed_time)

        # --- Vẽ giao diện --- #
        h, w = display_img.shape[:2]
        center_x, center_y = w // 2, h // 2
        
        # Khung oval hướng dẫn
        oval_w, oval_h = w // 3, h // 2
        cv2.ellipse(display_img, (center_x, center_y), (oval_w, oval_h), 0, 0, 360, (255, 255, 0), 2)

        # Đồng hồ đếm ngược
        timer_text = f"Time: {int(remaining_time)}s"
        cv2.putText(display_img, timer_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(display_img, "[Q] to Quit", (w - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # Thanh tiến trình
        progress = elapsed_time / RECORD_SECONDS
        cv2.rectangle(display_img, (0, h - 10), (int(progress * w), h), (0, 255, 0), -1)
        # --- Kết thúc vẽ giao diện --- #

        # Chỉ xử lý khi còn trong thời gian quay
        if remaining_time > 0:
            # Tự động chụp frame nếu có 1 mặt trong khung
            rec.detector_face.set_img_input(frame)
            faces = rec.detector_face.cropped_faces
            if faces is not None and len(faces) == 1:
                captured_frames.append(frame)
                # Có thể thêm hiệu ứng nháy xanh để báo hiệu đã chụp
                cv2.ellipse(display_img, (center_x, center_y), (oval_w, oval_h), 0, 0, 360, (0, 255, 0), 3)

        # Hiển thị
        cv2.imshow("Live Registration", display_img)

        if remaining_time <= 0:
            break # Hết giờ

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cleanup_and_exit(captured_anything=len(captured_frames) > 0)
            return

    # --- Xử lý sau khi quay xong --- #
    cam.release()
    cv2.destroyAllWindows()

    if not captured_frames:
        print("⚠️ Không có khung hình nào được ghi lại. Thoát.")
        cleanup_and_exit(captured_anything=False)
        return

    print(f"\nĐã quay xong. Bắt đầu xử lý {len(captured_frames)} khung hình đã chọn...")
    embeddings_buffer = []
    for i, cap_frame in enumerate(captured_frames):
        # Lấy embedding
        embed = rec.get_face_embedding(cap_frame)
        if len(embed) == 1:
            embeddings_buffer.append(embed[0])
            # Lưu ảnh đã chụp
            img_path = f"{dir_path}/capture_{i+1}.jpg"
            cv2.imwrite(img_path, cap_frame)
            print(f"Đã xử lý và lưu ảnh {i+1}/{len(captured_frames)}")

    if not embeddings_buffer:
        print("⚠️ Không thể trích xuất embedding từ các ảnh đã chụp. Thoát.")
        cleanup_and_exit(captured_anything=True) # Có ảnh nhưng ko có embedding
        return

    # Thêm vào DB
    embeds = np.array(embeddings_buffer)
    vt_db.add_emb(embeds, name, id)
    print(f"✅ Hoàn tất đăng ký! Đã thêm {len(embeds)} ảnh cho {name} với ID: {id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đăng ký khuôn mặt bằng cách quay video 30 giây.")
    parser.add_argument("--name", type=str, required=True, help="Tên người cần đăng ký")
    parser.add_argument("--id", type=int, required=True, help="ID người cần đăng ký")
    args = parser.parse_args()

    main(args.name, args.id)
