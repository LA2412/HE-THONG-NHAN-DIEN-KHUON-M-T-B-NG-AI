import cv2

for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"[OK] Camera {i} hoạt động.")
        cap.release()
    else:
        print(f"[FAIL] Camera {i} không hoạt động.")
