from __future__ import annotations

import os
import base64
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from src.core.recognition import Regconizer
from src import config as conf
from src.services import analytics_service, customer_service, face_service, order_service, product_service, user_service


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

recognizer = Regconizer()

user_service.ensure_default_admin()


def refresh_recognizer():
    global recognizer
    try:
        recognizer = Regconizer()
    except Exception as exc:
        app.logger.error("Không thể reload mô hình nhận diện: %s", exc)


def login_required(role: Optional[str] = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect(url_for("login"))
            if role and user.get("role") != role:
                flash("Bạn không có quyền truy cập trang này.", "danger")
                return redirect(url_for("home"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_globals():
    return {"current_year": datetime.utcnow().year}


@app.route("/")
def home():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("staff_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = user_service.authenticate(username, password)
        if user:
            session["user"] = {
                "id": user.get("id"),
                "username": user.get("username"),
                "role": user.get("role"),
                "full_name": user.get("full_name"),
                "email": user.get("email"),
            }
            flash("Đăng nhập thành công.", "success")
            return redirect(url_for("home"))
        flash("Sai tài khoản hoặc mật khẩu.", "danger")
    return render_template("login.html", title="Đăng nhập")


@app.post("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("login"))


@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    stats = order_service.sales_summary()
    metrics = analytics_service.recognition_metrics()
    frequent = analytics_service.frequent_customers()
    top_customers = analytics_service.top_customers()
    employee_stats = analytics_service.employee_performance()
    return render_template(
        "admin/dashboard.html",
        title="Bảng điều khiển Admin",
        stats=stats,
        metrics=metrics,
        frequent_customers=frequent,
        top_customers=top_customers,
        employee_stats=employee_stats,
    )


@app.route("/admin/users", methods=["GET", "POST"])
@login_required("admin")
def admin_users():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "create":
                user_service.create_user(
                    username=request.form["username"],
                    password=request.form["password"],
                    role=request.form.get("role", "staff"),
                    full_name=request.form.get("full_name", ""),
                    email=request.form.get("email", ""),
                    phone=request.form.get("phone", ""),
                )
                flash("Đã tạo tài khoản mới.", "success")
            elif action == "update":
                user_id = request.form["user_id"]
                user_service.update_user(
                    user_id,
                    full_name=request.form.get("full_name", ""),
                    email=request.form.get("email", ""),
                    phone=request.form.get("phone", ""),
                    role=request.form.get("role", "staff"),
                    is_active=int(request.form.get("is_active", "1")),
                )
                new_password = request.form.get("new_password")
                if new_password:
                    user_service.set_password(user_id, new_password)
                flash("Đã cập nhật tài khoản.", "success")
            elif action == "delete":
                user_id = request.form["user_id"]
                if user_id == session["user"]["id"]:
                    flash("Không thể tự xóa tài khoản của chính bạn.", "danger")
                else:
                    user_service.delete_user(user_id)
                    flash("Đã xóa tài khoản.", "info")
        except Exception as exc:
            flash(f"Lỗi: {exc}", "danger")
        return redirect(url_for("admin_users"))

    users = user_service.list_users()
    return render_template("admin/users.html", title="Quản lý tài khoản", users=users)


@app.route("/admin/products", methods=["GET", "POST"])
@login_required("admin")
def admin_products():
    if request.method == "POST":
        resource = request.form.get("resource")
        try:
            if resource == "category":
                product_service.create_category(
                    name=request.form["name"],
                    description=request.form.get("description", ""),
                )
                flash("Đã thêm danh mục.", "success")
            elif resource == "category-delete":
                product_service.delete_category(request.form["category_id"])
                flash("Đã xóa danh mục.", "info")
            elif resource == "product":
                product_service.create_product(
                    sku=request.form["sku"],
                    name=request.form["name"],
                    price=float(request.form.get("price", 0)),
                    stock=int(request.form.get("stock", 0)),
                    description=request.form.get("description", ""),
                    category_id=request.form.get("category_id") or None,
                    image_path=request.form.get("image_path", ""),
                    user_id=session["user"]["id"],
                )
                flash("Đã thêm sản phẩm.", "success")
            elif resource == "product-update":
                product_service.update_product(
                    request.form["product_id"],
                    user_id=session["user"]["id"],
                    name=request.form.get("name"),
                    price=float(request.form.get("price", 0)),
                    stock=int(request.form.get("stock", 0)),
                    category_id=request.form.get("category_id") or None,
                    is_active=bool(int(request.form.get("is_active", "1"))),
                    description=request.form.get("description"),
                )
                flash("Đã cập nhật sản phẩm.", "success")
            elif resource == "product-delete":
                product_service.delete_product(request.form["product_id"], user_id=session["user"]["id"])
                flash("Đã xóa sản phẩm.", "info")
        except Exception as exc:
            flash(f"Lỗi: {exc}", "danger")
        return redirect(url_for("admin_products", keyword=request.args.get("keyword", "")))

    keyword = request.args.get("keyword", "")
    categories = product_service.list_categories()
    products = product_service.search_products(keyword) if keyword else product_service.search_products("")
    return render_template(
        "admin/products.html",
        title="Quản lý sản phẩm",
        categories=categories,
        products=products,
    )


@app.route("/admin/faces", methods=["GET", "POST"])
@login_required("admin")
def admin_faces():
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "rename":
                face_service.rename_face(int(request.form["face_id"]), request.form["new_name"])
                flash("Đã đổi tên khuôn mặt.", "success")
                refresh_recognizer()
            elif action == "merge":
                primary_face_id = int(request.form["primary_face_id"])
                duplicate_face_id = int(request.form["duplicate_face_id"])
                if primary_face_id == duplicate_face_id:
                    flash("Vui lòng chọn hai Face ID khác nhau.", "danger")
                else:
                    added, dup = face_service.merge_profiles(primary_face_id, duplicate_face_id)
                    primary_customer = customer_service.get_customer_by_face_id(primary_face_id)
                    duplicate_customer = customer_service.get_customer_by_face_id(duplicate_face_id)
                    if primary_customer and duplicate_customer:
                        customer_service.merge_customers(primary_customer["id"], duplicate_customer["id"], user_id=session["user"]["id"])
                    elif duplicate_customer and not primary_customer:
                        customer_service.update_customer(duplicate_customer["id"], face_id=primary_face_id)
                    else:
                        customer_service.unlink_face(duplicate_face_id)
                    flash(f"Đã gộp hồ sơ {dup} vào {primary_face_id} (thêm {added} embedding).", "success")
                    refresh_recognizer()
            elif action == "delete":
                face_id = int(request.form["face_id"])
                face_service.remove_face(face_id)
                customer_service.unlink_face(face_id)
                flash("Đã xóa dữ liệu khuôn mặt.", "info")
                refresh_recognizer()
            elif action == "rebuild":
                folder = request.form.get("folder", "./images")
                reinit = request.form.get("reinit") == "1"
                face_service.rebuild_from_folder(folder, reinit=reinit)
                flash("Đã huấn luyện lại dữ liệu nhận diện.", "success")
                refresh_recognizer()
        except Exception as exc:
            flash(f"Lỗi: {exc}", "danger")
        return redirect(url_for("admin_faces"))

    faces = face_service.list_faces()
    return render_template("admin/faces.html", title="Quản lý dữ liệu nhận diện", faces=faces)


@app.route("/admin/reports")
@login_required("admin")
def admin_reports():
    orders = order_service.list_orders(limit=200)
    login_logs = user_service.login_logs()
    activity_logs = user_service.activity_logs()
    recognition = customer_service.recognition_history()
    return render_template(
        "admin/reports.html",
        title="Báo cáo & nhật ký",
        orders=orders,
        login_logs=login_logs,
        activity_logs=activity_logs,
        recognition=recognition,
    )


def _get_cart() -> Dict[str, Dict]:
    return session.setdefault("cart", {})


def _set_cart(cart: Dict[str, Dict]) -> None:
    session["cart"] = cart
    session.modified = True


def _get_recognition_cache() -> Dict[str, float]:
    return session.setdefault("recognition_cache", {})


@app.route("/staff")
@login_required("staff")
def staff_dashboard():
    keyword = request.args.get("keyword", "").strip()
    products: List[Dict] = product_service.search_products(keyword) if keyword else []
    catalog_products = product_service.search_products("")[:20]
    cart = _get_cart()
    cart_items = []
    total = 0.0
    for item in cart.values():
        line_total = item["price"] * item["quantity"]
        cart_items.append(
            {
                "product_id": item["product_id"],
                "name": item["name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "total": line_total,
            }
        )
        total += line_total

    registration = session.pop("registration_result", None)
    active_customer = session.get("active_customer")
    active_customer_info = None
    if active_customer:
        customer_id = active_customer.get("id")
        if customer_id:
            active_customer_info = customer_service.get_customer(customer_id) or None
        if not active_customer_info:
            fallback = {
                "id": active_customer.get("id"),
                "full_name": active_customer.get("full_name"),
                "face_id": active_customer.get("face_id"),
                "phone": active_customer.get("phone"),
                "email": active_customer.get("email"),
            }
            # Only expose fallback info if we have at least one meaningful field
            if any(value is not None for key, value in fallback.items() if key != "id"):
                active_customer_info = fallback

    purchase_history: List[Dict] = []
    if active_customer and active_customer.get("id"):
        purchase_history = order_service.list_orders(limit=5, customer_id=active_customer["id"])

    return render_template(
        "staff/dashboard.html",
        title="Quầy bán hàng",
        products=products,
        cart_items=cart_items,
        cart_total=total,
        registration=registration,
        active_customer_info=active_customer_info,
        purchase_history=purchase_history,
        catalog_products=catalog_products,
    )


@app.route("/staff/customers")
@login_required("staff")
def staff_customers():
    keyword = request.args.get("keyword", "").strip()
    customers = customer_service.list_customers(keyword)
    return render_template("staff/customers.html", title="Khách hàng", customers=customers)


@app.route("/staff/orders")
@login_required("staff")
def staff_orders():
    orders = order_service.list_orders(limit=100, staff_id=session["user"]["id"])
    return render_template("staff/orders.html", title="Đơn hàng của tôi", orders=orders)


@app.post("/staff/recognize/frame")
@login_required("staff")
def staff_recognize_frame():
    payload = request.get_json(silent=True)
    if not payload or "image" not in payload:
        return jsonify({"error": "Thiếu dữ liệu ảnh."}), 400

    image_b64 = payload["image"]
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return jsonify({"error": "Ảnh gửi lên không hợp lệ."}), 400

    np_buffer = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "Không thể đọc dữ liệu ảnh."}), 400

    results = recognizer.regcognize_face(frame)
    recognition_cache = _get_recognition_cache()
    now_ts = time.time()

    active_customer = session.get("active_customer")
    history_payload: List[Dict] = []
    matches: List[Dict] = []

    recognized_customer = None
    for dist, name, face_id in zip(results["Distances"], results["Names"], results["IDs"]):
        fid = int(face_id[0])
        distance_value = float(dist[0])
        is_recognized = distance_value <= conf.threshold_distance
        matches.append(
            {
                "distance": distance_value,
                "name": name[0],
                "id": fid,
                "recognized": is_recognized,
            }
        )
        if not is_recognized:
            continue

        customer = customer_service.get_customer_by_face_id(fid)
        if not customer:
            continue

        recognized_customer = customer
        cache_key = str(fid)
        last_seen = recognition_cache.get(cache_key, 0)
        if now_ts - last_seen > 10:
            customer_service.log_recognition_event(
                customer_id=customer["id"],
                staff_id=session["user"]["id"],
                confidence=distance_value,
                camera_id="POS-CAM",
            )
            recognition_cache[cache_key] = now_ts
            session.modified = True

        customer_payload = {
            "id": customer["id"],
            "full_name": customer.get("full_name"),
            "face_id": customer.get("face_id"),
            "phone": customer.get("phone"),
            "email": customer.get("email"),
        }

        if not active_customer or active_customer.get("id") != customer["id"]:
            active_customer = customer_payload
            history_payload = [
                {
                    "order_number": order.get("order_number"),
                    "created_at": order.get("created_at"),
                    "total_amount": order.get("total_amount", 0),
                }
                for order in order_service.list_orders(limit=5, customer_id=customer["id"])
            ]
            session["active_customer"] = customer_payload
            session["active_customer_last_seen"] = now_ts
            session.modified = True
        else:
            # refresh payload with newest customer details
            active_customer.update(customer_payload)
            history_payload = [
                {
                    "order_number": order.get("order_number"),
                    "created_at": order.get("created_at"),
                    "total_amount": order.get("total_amount", 0),
                }
                for order in order_service.list_orders(limit=5, customer_id=customer["id"])
            ]
            session["active_customer_last_seen"] = now_ts
            session.modified = True

        break

    # nếu không còn khách trong khung hình trong 5 giây -> clear
    last_seen_ts = session.get("active_customer_last_seen")
    if recognized_customer is None and last_seen_ts and now_ts - last_seen_ts > 5:
        session["active_customer"] = None
        session["active_customer_last_seen"] = None
        session.modified = True
        active_customer = None
        history_payload = []

    return jsonify(
        {
            "matches": matches,
            "active_customer": active_customer,
            "purchase_history": history_payload,
            "timestamp": now_ts,
        }
    )


@app.post("/staff/recognize/reset")
@login_required("staff")
def staff_reset_recognition():
    """
    Clear any active customer selection and reset recognition cache so the next frame
    starts with a clean state.
    """
    session.pop("active_customer", None)
    session.pop("active_customer_last_seen", None)
    session.pop("recognition_cache", None)
    session.modified = True
    return jsonify({"status": "reset"})


@app.post("/staff/register")
@login_required("staff")
def staff_register_customer():
    full_name = request.form.get("full_name", "").strip()
    if not full_name:
        flash("Vui lòng nhập tên khách hàng.", "danger")
        return redirect(url_for("staff_dashboard"))

    video_file = request.files.get("video")
    if not video_file or video_file.filename == "":
        flash("Vui lòng tải video 10 giây của khách hàng.", "danger")
        return redirect(url_for("staff_dashboard"))

    face_id = face_service.next_face_id()
    extension = Path(video_file.filename).suffix or ".mp4"
    destination = face_service.media_destination(face_id, full_name, "video", extension)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        video_file.save(destination)
        added = face_service.add_from_video(face_id, full_name, str(destination))
        customer_id = customer_service.create_customer(
            full_name=full_name,
            gender=request.form.get("gender", ""),
            phone=request.form.get("phone", ""),
            email=request.form.get("email", ""),
            notes=request.form.get("notes", ""),
            face_id=face_id,
        )
        session["registration_result"] = f"Đã đăng ký khách {full_name} với Face ID {face_id} (thu được {added} embedding)."
        session["active_customer"] = {
            "id": customer_id,
            "full_name": full_name,
            "face_id": face_id,
            "phone": request.form.get("phone", ""),
            "email": request.form.get("email", ""),
        }
        refresh_recognizer()
        flash("Đăng ký khách hàng mới thành công.", "success")
    except Exception as exc:
        if destination.exists():
            destination.unlink()
        flash(f"Lỗi đăng ký khách hàng: {exc}", "danger")
    return redirect(url_for("staff_dashboard"))


@app.post("/staff/customer/set")
@login_required("staff")
def staff_set_customer():
    customer_id = request.form.get("customer_id")
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or (
        request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
    )

    if not customer_id:
        session["active_customer"] = None
        session.modified = True
        message = "Đã chuyển sang chế độ khách vãng lai."
        if wants_json:
            return jsonify({"status": "cleared", "message": message})
        flash(message, "info")
        return redirect(url_for("staff_dashboard"))

    customer = customer_service.get_customer(customer_id)
    if not customer:
        if wants_json:
            return jsonify({"status": "error", "message": "Không tìm thấy khách hàng."}), 404
        flash("Không tìm thấy khách hàng.", "danger")
        return redirect(url_for("staff_dashboard"))

    active_payload = {
        "id": customer["id"],
        "full_name": customer.get("full_name"),
        "face_id": customer.get("face_id"),
        "phone": customer.get("phone"),
        "email": customer.get("email"),
    }
    session["active_customer"] = active_payload
    session.modified = True
    message = f"Đang phục vụ khách {customer.get('full_name') or customer.get('face_id')}."
    if wants_json:
        return jsonify({"status": "ok", "active_customer": active_payload, "message": message})
    flash(message, "success")
    return redirect(url_for("staff_dashboard"))


@app.post("/staff/customer/clear")
@login_required("staff")
def staff_clear_customer():
    session["active_customer"] = None
    session.modified = True
    flash("Đã bỏ chọn khách hàng, chuyển sang khách vãng lai.", "info")
    return redirect(url_for("staff_dashboard"))


@app.post("/staff/cart/add")
@login_required("staff")
def staff_add_to_cart():
    product_id = request.form.get("product_id")
    quantity = int(request.form.get("quantity", "1"))
    if not product_id:
        flash("Thiếu thông tin sản phẩm.", "danger")
        return redirect(url_for("staff_dashboard", keyword=request.args.get("keyword", "")))

    product = product_service.get_product(product_id)
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("staff_dashboard"))

    if quantity <= 0:
        flash("Số lượng phải lớn hơn 0.", "danger")
        return redirect(url_for("staff_dashboard"))

    cart = _get_cart()
    item = cart.get(product_id)
    if item:
        item["quantity"] += quantity
    else:
        cart[product_id] = {
            "product_id": product_id,
            "name": product.get("name"),
            "price": product.get("price", 0),
            "quantity": quantity,
            "stock": product.get("stock", 0),
        }
    _set_cart(cart)
    flash("Đã thêm vào giỏ hàng.", "success")
    return redirect(url_for("staff_dashboard", keyword=request.args.get("keyword", "")))


@app.post("/staff/cart/remove")
@login_required("staff")
def staff_remove_from_cart():
    product_id = request.form.get("product_id")
    cart = _get_cart()
    if product_id in cart:
        del cart[product_id]
        _set_cart(cart)
        flash("Đã xóa sản phẩm khỏi giỏ.", "info")
    return redirect(url_for("staff_dashboard"))


@app.post("/staff/cart/clear")
@login_required("staff")
def staff_clear_cart():
    session["cart"] = {}
    session.modified = True
    flash("Đã xóa giỏ hàng.", "info")
    return redirect(url_for("staff_dashboard"))


@app.post("/staff/cart/checkout")
@login_required("staff")
def staff_checkout():
    cart = _get_cart()
    if not cart:
        flash("Giỏ hàng trống.", "danger")
        return redirect(url_for("staff_dashboard"))

    payment_method = request.form.get("payment_method")
    if not payment_method:
        flash("Vui lòng chọn phương thức thanh toán.", "danger")
        return redirect(url_for("staff_dashboard"))

    active_customer = session.get("active_customer")
    customer_id = active_customer.get("id") if active_customer else None

    items = []
    for item in cart.values():
        items.append({"product_id": item["product_id"], "quantity": item["quantity"]})

    try:
        order_info = order_service.create_order(
            items=items,
            customer_id=customer_id,
            staff_id=session["user"]["id"],
            payment_method=payment_method,
            notes=request.form.get("notes", ""),
        )
        session["cart"] = {}
        session.modified = True
        flash(f"Tạo đơn hàng thành công: {order_info['order_number']}", "success")
    except Exception as exc:
        flash(f"Lỗi tạo đơn hàng: {exc}", "danger")
    return redirect(url_for("staff_dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=os.environ.get("FLASK_DEBUG") == "1")
