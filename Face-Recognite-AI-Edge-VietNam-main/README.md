# Hệ Thống Nhận Diện Khuôn Mặt Cho Bán Lẻ Thông Minh

Dự án mở rộng nền tảng nhận diện khuôn mặt ban đầu thành một giải pháp bán lẻ hoàn chỉnh với phân quyền rõ ràng giữa **quản trị viên** và **nhân viên bán hàng**. Giao diện điều khiển mới được xây dựng bằng **Flask + HTML/CSS thuần**, đảm bảo hiệu năng, dễ tùy biến và không phụ thuộc Streamlit. Hệ thống hỗ trợ nhận diện khách hàng, quản trị dữ liệu sản phẩm, khách hàng, nhật ký hoạt động và báo cáo doanh thu.

## Điểm Nổi Bật

- **Đăng nhập & phân quyền**: phiên đăng nhập bảo vệ bằng PBKDF2, hỗ trợ vai trò `admin` và `staff`.
- **Quản trị viên**:
  - Tạo, khóa/mở khóa tài khoản nhân viên, đổi mật khẩu.
  - Quản lý danh mục và sản phẩm, điều chỉnh tồn kho.
  - Quản trị dữ liệu nhận diện (đổi tên, xóa, gộp hồ sơ, tái huấn luyện).
  - Dashboard tổng quan: doanh số, khách thân thiết, hiệu suất nhân viên, nhật ký đăng nhập/hoạt động/nhận diện.
- **Nhân viên bán hàng**:
  - Làm việc trên dashboard HTML với thanh điều hướng bên trái, camera POS tự động bật và quét khuôn mặt liên tục.
  - Tự động nhận diện khách quen, hiển thị lịch sử mua, gợi ý sản phẩm cá nhân hóa.
  - Đăng ký khách mới bằng nút “Quay 10 giây đăng ký khuôn mặt”, lưu video, sinh embedding và tạo hồ sơ CRM.
  - Tìm kiếm sản phẩm, quản lý giỏ hàng, tạo đơn bán; hệ thống tự trừ tồn kho và ghi nhật ký.

## Kiến Trúc & Công Nghệ

- **Python**, **Flask**, **HTML/CSS** (giao diện quản trị và bán hàng).
- **MongoDB** (mặc định `mongodb://localhost:27017/deep-face-shop`) lưu trữ tài khoản, sản phẩm, đơn hàng, khách hàng, nhật ký.
- **FAISS** + **FaceNet** cho nhận diện khuôn mặt; **YOLO** cho phát hiện khuôn mặt.
- **OpenCV**, **NumPy** cho xử lý hình ảnh/video.

## Cấu Trúc Quan Trọng

```
.
├── app.py                     # Ứng dụng Flask chính (dashboard admin & staff)
├── templates/                 # Bộ giao diện HTML
├── static/css/style.css       # Bộ giao diện CSS
├── app_ui.py                  # Giao diện Tkinter cũ (tham khảo)
├── src/
│   ├── core/                  # Nhận diện, phát hiện, quản lý vector FAISS
│   ├── data/db.py             # Kết nối + chỉ mục MongoDB
│   ├── processing/            # Xử lý video/ảnh tạo embedding
│   ├── services/              # Lớp nghiệp vụ (user/product/order/customer/analytics/face)
├── database/
│   ├── face_index.faiss       # FAISS index
│   ├── map_id_name.json       # Map Face ID ↔ tên
│   └── data/                  # Video/ảnh gốc theo từng khách
└── legacy_scripts/            # Script hỗ trợ huấn luyện lại từ ảnh
```

## Cài Đặt Nhanh

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

> Lưu ý: `tensorflow`, `faiss-cpu`, `ultralytics` (và các phụ thuộc xử lý video như `opencv-python`) có thể mất thời gian cài đặt.

### Cấu hình MongoDB

- Mặc định ứng dụng kết nối `mongodb://localhost:27017/deep-face-shop`.
- Có thể thay đổi bằng biến môi trường:
  ```bash
  export MONGO_URI="mongodb://<user>:<pass>@<host>:<port>/<database>"
  ```
- Đảm bảo MongoDB đang chạy trước khi khởi động ứng dụng.

## Khởi Chạy Ứng Dụng HTML

```bash
./start.sh
# hoặc
python app.py
```

- Tài khoản mặc định: `admin` / `Admin@123`.
- Sau khi đăng nhập:
  - **Admin** điều hướng qua sidebar tới Tổng quan, Tài khoản, Sản phẩm, Dữ liệu nhận diện, Báo cáo.
  - **Staff** sử dụng mục *Bán hàng* để nhận diện khách hàng qua ảnh/clip, quản lý giỏ hàng và tạo đơn; mục *Khách hàng* và *Lịch sử đơn hàng* để tra cứu thông tin.

## Quy Trình Bán Hàng Cho Nhân Viên

1. Mở mục **Bán hàng**, hệ thống bật camera và nhận diện khách quen.
2. Nếu khách quen:
   - Hiển thị hồ sơ CRM, lịch sử ghé, tổng chi tiêu, gợi ý sản phẩm dựa trên lịch sử mua.
3. Nếu khách mới:
   - Nhấn **“Quay 10 giây đăng ký”**, camera ghi video, hệ thống tạo embedding, lưu video và tạo hồ sơ khách.
4. Tìm kiếm sản phẩm → thêm vào giỏ → chọn thanh toán → **Tạo đơn hàng**.
5. Đơn hàng được ghi vào MongoDB, tồn kho trừ tự động, nhật ký hoạt động cập nhật.

## Quản Trị Dữ Liệu Nhận Diện

- **Đổi tên**: cập nhật map Face ID ↔ tên và đồng bộ thư mục dữ liệu gốc.
- **Gộp hồ sơ**: chuyển embedding/video/ảnh từ ID trùng vào ID chính, gom dữ liệu CRM, tránh trùng khách.
- **Xóa**: loại bỏ embedding khỏi FAISS, xóa dữ liệu video/ảnh, gỡ liên kết trong CRM.
- **Đào tạo lại**: dùng thư mục ảnh phân loại sẵn (`./images/{id}_{name}`) để tái tạo database.

## Giao Diện Tkinter Cũ

File `app_ui.py` vẫn được giữ lại để tham khảo hoặc dùng trong môi trường không hỗ trợ trình duyệt. Tuy nhiên, toàn bộ chức năng mới (quản lý tài khoản, sản phẩm, báo cáo, bán hàng) nằm trong ứng dụng Flask HTML.

## Hỗ Trợ & Đóng Góp

- Thêm mô hình, cải thiện pipeline nhận diện: cập nhật trong `src/core`.
- Viết test/fixture cho lớp dịch vụ: `src/services`.
- Báo lỗi & đề xuất qua Issues/PR.

Chúc bạn triển khai thành công hệ thống nhận diện cho cửa hàng thông minh! 🎉
