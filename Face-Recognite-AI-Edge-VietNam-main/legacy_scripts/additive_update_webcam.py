"""
Cập nhật (thêm) embedding cho một ID đã có bằng cách chụp 9 hướng.
"""

import cv2
import os
import sys
import numpy as np
import shutil
import argparse
import json

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.recognition import Regconizer
from src.core.vectordb import VectorBD
from src.utils import check_is_id_exist
from src import config as conf

def get_name_from_id(id: int) -> str | None:
    """Lấy tên từ ID trong file map."""
    path = conf.path_json_id_name
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get(str(id))

def main(id: int):
    if not check_is_id_exist(id):
        print(f"❌ ID {id} không tồn tại trong database. Không thể cập nhật.")
        return

    name = get_name_from_id(id)
    if not name:
        print(f"❌ Không tìm thấy tên cho ID {id} trong file map.")
        return

    # Tạo thư mục lưu ảnh
    dir_path = f'./images/{id}_{name}'
    os.makedirs(dir_path, exist_ok=True)

    # Thứ tự chụp các hướng (bao gồm chéo)
    directions = [
        'mid', 'left', 'right', 'up', 'down',
        'up_left', 'up_right', 'down_left', 'down_right'
    ]
    current_idx = 0

    # Khởi tạo nhận diện và DB
    rec = Regconizer()
    vt_db = VectorBD()

    # Mở camera
    cam = cv2.VideoCapture(0)

    def cleanup_and_exit(remove_folder=False):
        cam.release()
        cv2.destroyAllWindows()
        if remove_folder and os.path.exists(dir_path):
            # In an additive update, we might not want to remove the folder
            # shutil.rmtree(dir_path)
            print(f"❌ Phát hiện nhiều khuôn mặt. Dữ liệu chụp lần này sẽ không được lưu.")
        print("Thoát chương trình")
        exit(0)

    print("👉 CẬP NHẬT THÊM ẢNH. Nhìn theo thứ tự: mid → left → right → up → down | Nhấn: [P] chụp, [Q] thoát")

    embeddings_buffer = []

    while True:
        ret, frame = cam.read()
        if not ret:
            print("Không đọc được khung hình từ camera")
            cleanup_and_exit(remove_folder=False)
        frame = cv2.flip(frame, 1)

        # Tính embedding và cập nhật ảnh có bbox để hiển thị
        embed = rec.get_face_embedding(frame)
        display_img = rec.detector_face.img_with_bbs if hasattr(rec, 'detector_face') else frame

        # Overlay UI: hướng hiện tại, tiến độ, hướng dẫn phím
        h, w = display_img.shape[:2]
        bar_w = int((current_idx / len(directions)) * w)
        cv2.rectangle(display_img, (0, h-10), (bar_w, h), (0, 255, 0), -1)
        cur_dir = directions[current_idx]
        cv2.putText(display_img, f"Direction: {cur_dir}  ({current_idx+1}/{len(directions)})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2, cv2.LINE_AA)
        cv2.putText(display_img, "[P] capture  [Q] quit",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)

        # Hiển thị khung hình
        cv2.imshow("Camera", display_img)

        # Đọc phím một lần mỗi vòng
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cleanup_and_exit(remove_folder=False)
        if key == ord('p'):
            if len(embed) == 1:
                # Lưu ảnh theo hướng hiện tại
                # Create a unique name for additional images
                img_count = len(os.listdir(dir_path)) + 1
                img_path = f"{dir_path}/{cur_dir}_{img_count}.jpg"
                cv2.imwrite(img_path, frame)

                # Lưu embedding
                embeddings_buffer.append(embed[0])
                print(f"Đã lưu {cur_dir} → {img_path}")

                # Tiến hướng kế tiếp
                current_idx += 1
                if current_idx >= len(directions):
                    # Đủ 9 hướng → lưu DB
                    embeds = np.array(embeddings_buffer)
                    vt_db.add_more_emb(embeds, id)
                    print(f"✅ Hoàn tất cập nhật và đã thêm {len(embeds)} embeddings mới vào ID {id}.")
                    cleanup_and_exit(remove_folder=False)
            elif len(embed) == 0:
                print("⚠️ Không phát hiện gương mặt nào. Hãy đưa mặt vào khung.")
            else:
                print("⚠️ Tồn tại nhiều hơn 1 gương mặt. Hãy đảm bảo chỉ có 1 người trong khung.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="ID người cần cập nhật (thêm ảnh)")
    args = parser.parse_args()

    main(args.id)
