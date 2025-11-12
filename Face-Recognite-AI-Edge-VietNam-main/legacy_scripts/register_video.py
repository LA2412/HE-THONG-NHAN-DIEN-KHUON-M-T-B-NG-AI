"""
Đăng ký khuôn mặt từ video và lưu embeddings.
"""

import cv2
import os
import sys
import numpy as np
import argparse
import time

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.recognition import Regconizer
from src.core.vectordb import VectorBD
from src.utils import check_is_id_exist

def main(name: str, id: int, video_path: str, frame_skip: int):
    if not os.path.exists(video_path):
        print(f"❌ Lỗi: Không tìm thấy file video tại '{video_path}'")
        return

    if check_is_id_exist(id):
        print(f"❌ ID {id} đã tồn tại trong database. Hãy chọn ID khác.")
        return

    # Khởi tạo nhận diện và DB
    rec = Regconizer()
    vt_db = VectorBD()

    # Mở file video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Lỗi: Không thể mở file video '{video_path}'")
        return

    embeddings_buffer = []
    frame_count = 0
    registered_face_count = 0
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"👉 Bắt đầu xử lý video: {video_path}")
    print(f"Tổng số khung hình: {total_frames}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # Kết thúc video

        frame_count += 1
        
        # Bỏ qua các khung hình để tăng tốc độ xử lý
        if frame_count % frame_skip != 0:
            continue

        # Lấy embedding từ khung hình hiện tại
        embeds = rec.get_face_embedding(frame)

        # Chỉ xử lý nếu phát hiện được 1 khuôn mặt
        if len(embeds) == 1:
            embeddings_buffer.append(embeds[0])
            registered_face_count += 1
            
            # Hiển thị tiến trình
            progress = int((frame_count / total_frames) * 50) # 50-char progress bar
            print(f"\r[{'=' * progress}{' ' * (50 - progress)}] {frame_count}/{total_frames} | Đã nhận diện {registered_face_count} khuôn mặt", end="")

        elif len(embeds) > 1:
            print(f"\n⚠️ Cảnh báo tại khung hình {frame_count}: Phát hiện nhiều hơn 1 khuôn mặt. Bỏ qua...")
        # Không cần thông báo nếu không có khuôn mặt nào, vì video có thể có những đoạn không chứa mặt

    print(f"\n✅ Xử lý video hoàn tất. Tìm thấy {registered_face_count} khuôn mặt hợp lệ.")

    # Giải phóng tài nguyên video
    cap.release()

    # Lưu embeddings vào DB
    if embeddings_buffer:
        embeds_to_save = np.array(embeddings_buffer)
        vt_db.add_emb(embeds_to_save, name, id)
        print(f"✅ Đã đăng ký thành công người '{name}' với ID {id} và lưu {len(embeds_to_save)} embeddings vào database.")
    else:
        print("❌ Không tìm thấy khuôn mặt nào trong video để đăng ký.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đăng ký khuôn mặt từ video.")
    parser.add_argument("--name", type=str, required=True, help="Tên người cần đăng ký")
    parser.add_argument("--id", type=int, required=True, help="ID người cần đăng ký")
    parser.add_argument("--video_path", type=str, required=True, help="Đường dẫn tới file video")
    parser.add_argument("--frame_skip", type=int, default=5, help="Bỏ qua n khung hình để tăng tốc độ xử lý. Mặc định là 5.")
    args = parser.parse_args()

    main(args.name, args.id, args.video_path, args.frame_skip)
