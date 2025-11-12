"""
Main UI application for Face Recognition, built with Tkinter.
Refactored to support new data management and processing workflow.
Now includes camera selection functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import shutil
import cv2
import time
import numpy as np
import threading
from PIL import Image, ImageTk

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.vectordb import VectorBD
from src.core.recognition import Regconizer
from src.utils import check_is_id_exist, get_name_from_id, find_available_cameras
from src.processing import video_processor, image_processor
from legacy_scripts import create_database as create_vt_db # Keep for Initialize DB

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Hệ thống nhận diện khuôn mặt")
        self.root.geometry("400x400") # Increased height for settings button

        self.db = VectorBD()

        # --- Camera Configuration ---
        self.available_cameras = find_available_cameras()
        self.selected_camera_id = tk.IntVar()
        if not self.available_cameras:
            messagebox.showerror("Lỗi Camera", "Không tìm thấy camera nào! Các chức năng live sẽ bị vô hiệu hóa.")
            self.selected_camera_id.set(-1) # Use -1 to indicate no camera
        elif 1 in self.available_cameras: # Default to user's preferred camera 1 if available
            self.selected_camera_id.set(1)
        else:
            self.selected_camera_id.set(self.available_cameras[0]) # Default to the first camera found

        # --- UI Style and Layout ---
        style = ttk.Style()
        style.configure("TButton", font=("Helvetica", 12), padding=10)

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill=tk.BOTH)

        self.live_rec_button = ttk.Button(main_frame, text="Nhận diện khuôn mặt", command=self.open_recognition_window)
        self.live_rec_button.pack(expand=True, fill=tk.BOTH, pady=5)
        
        ttk.Button(main_frame, text="Đăng ký khuôn mặt mới", command=self.open_register_window).pack(expand=True, fill=tk.BOTH, pady=5)
        ttk.Button(main_frame, text="Cập nhật khuôn mặt đã có", command=self.open_update_window).pack(expand=True, fill=tk.BOTH, pady=5)
        ttk.Button(main_frame, text="Xóa khuôn mặt", command=self.open_delete_window).pack(expand=True, fill=tk.BOTH, pady=5)
        ttk.Button(main_frame, text="Khởi tạo DB từ ảnh", command=self.open_db_window).pack(expand=True, fill=tk.BOTH, pady=5)
        ttk.Button(main_frame, text="Cài đặt Camera", command=self.open_settings_window).pack(expand=True, fill=tk.BOTH, pady=5)

        if self.selected_camera_id.get() == -1:
            self.live_rec_button.config(state="disabled")

    def open_settings_window(self):
        win = tk.Toplevel(self.root)
        win.title("Cài đặt Camera")

        ttk.Label(win, text="Chọn camera để sử dụng:").pack(padx=10, pady=10)

        cam_combobox = ttk.Combobox(win, textvariable=self.selected_camera_id, state="readonly")
        cam_combobox['values'] = self.available_cameras
        cam_combobox.pack(padx=10, pady=5)

        def save_settings():
            messagebox.showinfo("Đã lưu", f"Đã chọn camera mặc định là ID: {self.selected_camera_id.get()}")
            win.destroy()

        ttk.Button(win, text="Lưu", command=save_settings).pack(pady=10)

    def open_recognition_window(self):
        win = tk.Toplevel(self.root)
        win.title("Nhận diện thời gian thực")

        video_label = ttk.Label(win)
        video_label.pack(padx=10, pady=10)

        stop_event = threading.Event()
        
        def _video_loop():
            reg = Regconizer()
            cam_id = self.selected_camera_id.get()
            cam = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
            if not cam.isOpened():
                messagebox.showerror("Lỗi Camera", f"Không thể mở camera ID {cam_id}.", parent=win)
                return

            while not stop_event.is_set():
                ret, frame = cam.read()
                if not ret: time.sleep(0.1); continue
                
                frame = cv2.flip(frame, 1)
                reg.regcognize_face(frame)
                vis_frame = reg.img_with_bbs if reg.img_with_bbs is not None else frame

                img = cv2.cvtColor(vis_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)
                imgtk = ImageTk.PhotoImage(image=img)
                
                video_label.imgtk = imgtk
                video_label.configure(image=imgtk)

            cam.release()

        def on_close():
            stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        video_thread = threading.Thread(target=_video_loop)
        video_thread.daemon = True
        video_thread.start()

    def _get_next_data_version(self, data_path):
        if not os.path.isdir(data_path): return 1
        existing_files = os.listdir(data_path)
        if not existing_files: return 1
        max_version = 0
        for f in existing_files:
            try:
                version_str = f.split('_L')[-1].split('.')[0]
                version = int(version_str)
                if version > max_version: max_version = version
            except (ValueError, IndexError): continue
        return max_version + 1

    def _record_live_video(self, save_path):
        RECORD_SECONDS = 30
        cam_id = self.selected_camera_id.get()
        cam = cv2.VideoCapture(cam_id, cv2.CAP_V4L2)
        if not cam.isOpened():
            messagebox.showerror("Lỗi Camera", f"Không thể mở camera ID {cam_id}. Hãy chắc chắn nó không được dùng bởi ứng dụng khác.")
            return False

        width, height = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cam.get(cv2.CAP_PROP_FPS); fps = fps if fps > 0 else 30

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(save_path, fourcc, fps, (width, height))

        start_time = time.time()
        while True:
            ret, frame = cam.read()
            if not ret: break

            display_img = frame.copy()
            elapsed_time = time.time() - start_time
            remaining_time = max(0, RECORD_SECONDS - elapsed_time)

            h, w = display_img.shape[:2]
            cv2.ellipse(display_img, (w//2, h//2), (w//3, h//2), 0, 0, 360, (255, 255, 0), 2)
            timer_text = f"Time: {int(remaining_time)}s"
            cv2.putText(display_img, timer_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(display_img, "[Q] to Quit", (w - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            progress = elapsed_time / RECORD_SECONDS
            cv2.rectangle(display_img, (0, h - 10), (int(progress * w), h), (0, 255, 0), -1)

            cv2.imshow("Live Recording", display_img)
            writer.write(frame)

            if remaining_time <= 0: break
            if cv2.waitKey(1) & 0xFF == ord('q'): break
        
        cam.release(); writer.release(); cv2.destroyAllWindows()
        return True

    def _process_and_save(self, id, name, source_type, source_path, is_update=False):
        if source_type == 'video': embeddings = video_processor.process_video(source_path)
        elif source_type == 'image': embeddings = image_processor.process_image_folder(source_path)
        else: return

        if embeddings.size == 0: return messagebox.showwarning("Không có dữ liệu", "Không tìm thấy khuôn mặt hợp lệ nào trong dữ liệu đầu vào.")

        try:
            if is_update: self.db.add_more_emb(embeddings, id)
            else: self.db.add_emb(embeddings, name, id)
            messagebox.showinfo("Thành công", f"Đã xử lý và lưu thành công {len(embeddings)} khuôn mặt cho ID: {id} - {name}")
        except Exception as e: messagebox.showerror("Lỗi Database", f"Có lỗi xảy ra khi lưu dữ liệu: {e}")

    def open_register_window(self): self._open_data_source_window(is_update=False)
    def open_update_window(self): self._open_data_source_window(is_update=True)

    def _open_data_source_window(self, is_update):
        title_prefix = "Cập nhật" if is_update else "Đăng ký"
        win = tk.Toplevel(self.root); win.title(f"{title_prefix} - Bước 1: Nhập thông tin")

        step1_frame = ttk.Frame(win, padding="10"); step1_frame.pack(fill="both", expand=True)
        ttk.Label(step1_frame, text="ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        id_entry = ttk.Entry(step1_frame); id_entry.grid(row=0, column=1, padx=5, pady=5)

        name_entry = None
        if not is_update: 
            ttk.Label(step1_frame, text="Tên:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            name_entry = ttk.Entry(step1_frame); name_entry.grid(row=1, column=1, padx=5, pady=5)

        def go_to_step_2():
            id_val_str = id_entry.get()
            if not id_val_str: return messagebox.showerror("Lỗi", "ID không được để trống.", parent=win)
            try:
                id_val = int(id_val_str)
                name_val = ""
                if is_update:
                    if not check_is_id_exist(id_val): return messagebox.showerror("Lỗi", f"ID {id_val} không tồn tại.", parent=win)
                    name_val = get_name_from_id(id_val)
                else:
                    name_val = name_entry.get()
                    if not name_val: return messagebox.showerror("Lỗi", "Tên không được để trống.", parent=win)
                    if check_is_id_exist(id_val): return messagebox.showerror("Lỗi", f"ID {id_val} đã tồn tại.", parent=win)

                step1_frame.pack_forget()
                win.title(f"{title_prefix} - Bước 2: Chọn nguồn")
                step2_frame = ttk.Frame(win, padding="10"); step2_frame.pack(fill="both", expand=True)
                ttk.Label(step2_frame, text=f"Đối tượng: {name_val} (ID: {id_val})").pack(pady=10)

                def on_live_cam():
                    video_dir = os.path.join('database', 'data', 'video', f'{id_val}_{name_val}')
                    os.makedirs(video_dir, exist_ok=True)
                    version = self._get_next_data_version(video_dir)
                    save_path = os.path.join(video_dir, f'{id_val}_{name_val}_L{version}.mp4')
                    win.destroy()
                    if self._record_live_video(save_path): self._process_and_save(id_val, name_val, 'video', save_path, is_update)

                def on_video_file():
                    filepath = filedialog.askopenfilename(title="Chọn file video", filetypes=[("Video files", "*.mp4 *.avi")])
                    if not filepath: return
                    video_dir = os.path.join('database', 'data', 'video', f'{id_val}_{name_val}')
                    os.makedirs(video_dir, exist_ok=True)
                    version = self._get_next_data_version(video_dir)
                    save_path = os.path.join(video_dir, f'{id_val}_{name_val}_L{version}.mp4')
                    shutil.copy(filepath, save_path); win.destroy()
                    self._process_and_save(id_val, name_val, 'video', save_path, is_update)

                def on_image_folder():
                    folderpath = filedialog.askdirectory(title="Chọn thư mục ảnh")
                    if not folderpath: return
                    image_dir = os.path.join('database', 'data', 'image', f'{id_val}_{name_val}')
                    if os.path.exists(image_dir): [shutil.copy(os.path.join(folderpath, item), image_dir) for item in os.listdir(folderpath)]
                    else: shutil.copytree(folderpath, image_dir)
                    win.destroy()
                    self._process_and_save(id_val, name_val, 'image', image_dir, is_update)

                live_button = ttk.Button(step2_frame, text="Trực tiếp (Live Webcam)", command=on_live_cam)
                live_button.pack(fill="x", padx=20, pady=5)
                ttk.Button(step2_frame, text="Từ File Video", command=on_video_file).pack(fill="x", padx=20, pady=5)
                ttk.Button(step2_frame, text="Từ Thư mục ảnh", command=on_image_folder).pack(fill="x", padx=20, pady=5)
                if self.selected_camera_id.get() == -1: live_button.config(state="disabled")

            except ValueError: messagebox.showerror("Lỗi", "ID phải là một con số.", parent=win)
            except Exception as e: messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}", parent=win)

        ttk.Button(step1_frame, text="Tiếp tục", command=go_to_step_2).grid(row=2, column=0, columnspan=2, pady=10)

    def open_delete_window(self):
        win = tk.Toplevel(self.root); win.title("Xóa khuôn mặt")
        ttk.Label(win, text="ID cần xóa:").pack(pady=5)
        id_entry = ttk.Entry(win); id_entry.pack(pady=5, padx=20, fill="x")

        def on_submit():
            id_val_str = id_entry.get()
            if not id_val_str: return
            try:
                id_val = int(id_val_str)
                if not check_is_id_exist(id_val): return messagebox.showerror("Lỗi", f"ID {id_val} không tồn tại.", parent=win)
                name_val = get_name_from_id(id_val)
                if not messagebox.askyesno("Xác nhận", f"Bạn có chắc chắn muốn xóa vĩnh viễn ID {id_val} - {name_val}?\nMọi dữ liệu, bao gồm cả ảnh và video gốc, sẽ bị xóa.", parent=win): return
                self.db.remove_emb(id_val, name_val)
                messagebox.showinfo("Thành công", f"Đã xóa hoàn toàn ID {id_val} - {name_val}.", parent=win)
                win.destroy()
            except ValueError: messagebox.showerror("Lỗi", "ID phải là một con số.", parent=win)
            except Exception as e: messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}", parent=win)

        ttk.Button(win, text="Xóa", command=on_submit).pack(pady=10)

    def open_db_window(self):
        win = tk.Toplevel(self.root); win.title("Khởi tạo DB từ ảnh")
        ttk.Label(win, text="Chức năng này giữ nguyên logic cũ.").pack(pady=20)
        ttk.Label(win, text="Nó sẽ quét 1 thư mục chứa nhiều thư mục con dạng ID_Tên.").pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()