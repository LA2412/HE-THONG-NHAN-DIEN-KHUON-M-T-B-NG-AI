(() => {
  const CAPTURE_INTERVAL_MS = 2000;
  let videoStream = null;
  let captureTimer = null;
  let isProcessing = false;
  let currentActiveCustomer = null;

  const videoEl = document.getElementById("camera-stream");
  const startBtn = document.getElementById("start-recognition");
  const stopBtn = document.getElementById("stop-recognition");
  const statusEl = document.getElementById("recognition-status");
  const matchesList = document.getElementById("recognition-matches");
  const activePanel = document.getElementById("active-customer-panel");
  const actionsContainer = document.getElementById("recognition-actions");
  const useBtn = document.getElementById("use-customer-btn");
  const resetBtn = document.getElementById("reset-recognition-btn");
  const recognitionAlert = document.getElementById("recognition-alert");
  const historyContainer = document.getElementById("purchase-history");
  const posWorkspace = document.getElementById("pos-workspace");
  const lockOverlay = document.getElementById("pos-lock-overlay");

  const profileIdInput = document.getElementById("customer-profile-id");
  const profileNameInput = document.getElementById("customer-profile-name");
  const profilePhoneInput = document.getElementById("customer-profile-phone");
  const profileEmailInput = document.getElementById("customer-profile-email");
  const profileFaceIdInput = document.getElementById("customer-profile-face-id");

  function setStatus(message, type = "info") {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.dataset.status = type;
  }

  function showRecognitionAlert(message, variant = "info") {
    if (!recognitionAlert) return;
    recognitionAlert.textContent = message;
    recognitionAlert.classList.remove("success", "error");
    if (variant === "success") {
      recognitionAlert.classList.add("success");
    } else if (variant === "error") {
      recognitionAlert.classList.add("error");
    }
  }

  function setWorkspaceLock(locked) {
    if (!posWorkspace) return;
    posWorkspace.classList.toggle("pos-right--locked", locked);
    posWorkspace.dataset.locked = locked ? "1" : "0";
    if (lockOverlay) {
      lockOverlay.hidden = !locked;
    }
    if (locked) {
      posWorkspace.querySelectorAll(".card").forEach((card) => {
        card.setAttribute("aria-disabled", "true");
      });
    } else {
      posWorkspace.querySelectorAll(".card").forEach((card) => {
        card.removeAttribute("aria-disabled");
      });
    }
  }

  function populateCustomerForm(data) {
    if (!data) {
      clearCustomerForm();
      return;
    }
    if (profileIdInput) profileIdInput.value = data.id || "";
    if (profileNameInput) profileNameInput.value = data.full_name || "";
    if (profilePhoneInput) profilePhoneInput.value = data.phone || "";
    if (profileEmailInput) profileEmailInput.value = data.email || "";
    if (profileFaceIdInput) profileFaceIdInput.value = data.face_id || "";
  }

  function clearCustomerForm() {
    if (profileIdInput) profileIdInput.value = "";
    if (profileNameInput) profileNameInput.value = "";
    if (profilePhoneInput) profilePhoneInput.value = "";
    if (profileEmailInput) profileEmailInput.value = "";
    if (profileFaceIdInput) profileFaceIdInput.value = "";
  }

  function renderCustomerSummary(data) {
    if (!activePanel) return;
    activePanel.innerHTML = "";
    if (data && (data.full_name || data.face_id)) {
      activePanel.dataset.has = "1";
      const overview = document.createElement("dl");
      overview.className = "customer-overview";
      const items = [
        { label: "Họ tên", value: data.full_name || `Face ID ${data.face_id || "—"}`, id: "active-customer-name" },
        { label: "Face ID", value: data.face_id || "—", id: "active-customer-face-id" },
        { label: "Điện thoại", value: data.phone || "—", id: "active-customer-phone" },
        { label: "Email", value: data.email || "—", id: "active-customer-email" },
      ];
      items.forEach((item) => {
        const wrapper = document.createElement("div");
        const dt = document.createElement("dt");
        dt.textContent = item.label;
        const dd = document.createElement("dd");
        dd.textContent = item.value || "—";
        if (item.id) {
          dd.id = item.id;
        }
        wrapper.append(dt, dd);
        overview.append(wrapper);
      });
      activePanel.appendChild(overview);
    } else {
      activePanel.dataset.has = "0";
      const placeholder = document.createElement("p");
      placeholder.id = "active-customer-placeholder";
      placeholder.className = "muted";
      placeholder.textContent = "Chưa nhận diện khách hàng.";
      activePanel.appendChild(placeholder);
    }
  }

  function updateActiveCustomer(data) {
    currentActiveCustomer = data && (data.full_name || data.face_id) ? data : null;
    renderCustomerSummary(currentActiveCustomer);
    const hasCustomer = Boolean(currentActiveCustomer && currentActiveCustomer.id);
    if (actionsContainer) {
      actionsContainer.hidden = !hasCustomer;
    }
    if (useBtn) {
      if (hasCustomer) {
        useBtn.disabled = false;
        useBtn.dataset.customerId = currentActiveCustomer.id;
      } else {
        useBtn.disabled = true;
        delete useBtn.dataset.customerId;
      }
    }
  }

  function updatePurchaseHistory(orders = []) {
    if (!historyContainer) return;
    if (!Array.isArray(orders) || orders.length === 0) {
      historyContainer.innerHTML = '<p class="muted">Chưa có lịch sử mua hàng.</p>';
      return;
    }
    const rows = orders
      .map(
        (order) => `
          <tr>
            <td>${order.order_number || "—"}</td>
            <td>${order.created_at || "—"}</td>
            <td>${Number(order.total_amount || 0).toLocaleString()} đ</td>
          </tr>
        `
      )
      .join("");
    historyContainer.innerHTML = `
      <table class="table small">
        <thead>
          <tr>
            <th>Mã đơn</th>
            <th>Ngày</th>
            <th>Giá trị</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function updateMatches(matches = []) {
    if (!matchesList) return;
    matchesList.innerHTML = "";
    if (!matches.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Chưa nhận diện được khuôn mặt.";
      matchesList.appendChild(li);
      return;
    }
    matches.forEach((match) => {
      const li = document.createElement("li");
      const recognized = match.recognized ? "✔" : "✖";
      li.innerHTML = `
        <span class="match-name">${match.name || "Unknown"}</span>
        <span class="match-meta">Face ID: ${match.id}</span>
        <span class="match-meta">Khoảng cách: ${Number(match.distance).toFixed(2)}</span>
        <span class="match-flag ${match.recognized ? "ok" : "fail"}">${recognized}</span>
      `;
      matchesList.appendChild(li);
    });
  }

  async function syncActiveCustomer(customerId) {
    if (!customerId) return;
    try {
      const formData = new FormData();
      formData.append("customer_id", customerId);
      await fetch("/staff/customer/set", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
      });
    } catch (error) {
      console.error("Không thể đồng bộ khách hàng đang phục vụ:", error);
    }
  }

  async function captureFrame() {
    if (!videoEl || !videoStream || isProcessing) return;
    if (!videoEl.videoWidth || !videoEl.videoHeight) return;

    const canvas = document.createElement("canvas");
    canvas.width = videoEl.videoWidth;
    canvas.height = videoEl.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

    isProcessing = true;
    try {
      const response = await fetch("/staff/recognize/frame", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ image: dataUrl }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Không nhận diện được khuôn mặt.");
      }

      updateMatches(result.matches || []);
      updateActiveCustomer(result.active_customer || null);
      updatePurchaseHistory(result.purchase_history || []);

      if (currentActiveCustomer && currentActiveCustomer.id) {
        const { full_name: name, face_id: faceId } = currentActiveCustomer;
        const displayName = name ? name : faceId ? `Face ID ${faceId}` : "khách hàng";
        const faceSuffix = faceId ? ` – Face ID ${faceId}` : "";
        showRecognitionAlert(`Đã nhận diện khách hàng ${displayName}${faceSuffix}.`, "success");
        setStatus("Đã nhận diện khách hàng.", "success");
        stopRecognition(false);
      } else {
        showRecognitionAlert("Chưa nhận diện khách hàng.", "info");
        setStatus("Đang quét khuôn mặt...", "info");
      }
    } catch (error) {
      console.error(error);
      showRecognitionAlert(error.message || "Lỗi nhận diện.", "error");
      setStatus(error.message || "Lỗi nhận diện.", "error");
    } finally {
      isProcessing = false;
    }
  }

  async function startRecognition(autoStart = false) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Trình duyệt không hỗ trợ camera.", "error");
      showRecognitionAlert("Trình duyệt không hỗ trợ camera.", "error");
      return;
    }
    if (videoStream) {
      return;
    }
    try {
      videoStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      if (videoEl) {
        videoEl.srcObject = videoStream;
        await videoEl.play();
      }
      setStatus("Đang quét khuôn mặt...", "info");
      startBtn && (startBtn.disabled = true);
      stopBtn && (stopBtn.disabled = false);
      captureTimer = window.setInterval(captureFrame, CAPTURE_INTERVAL_MS);
      captureFrame();
    } catch (error) {
      console.error(error);
      setStatus("Không thể truy cập camera. Hãy cấp quyền và thử lại.", "error");
      showRecognitionAlert("Không thể bật camera. Vui lòng kiểm tra quyền truy cập.", "error");
      if (!autoStart) {
        alert("Không thể bật camera. Vui lòng kiểm tra quyền truy cập.");
      }
    }
  }

  function stopRecognition(showMessage = true) {
    if (captureTimer) {
      window.clearInterval(captureTimer);
      captureTimer = null;
    }
    if (videoStream) {
      videoStream.getTracks().forEach((track) => track.stop());
      videoStream = null;
    }
    startBtn && (startBtn.disabled = false);
    stopBtn && (stopBtn.disabled = true);
    if (showMessage) {
      setStatus("Camera đã tắt.", "info");
    }
  }

  async function resetRecognition() {
    try {
      if (window.resetRecognitionUrl) {
        await fetch(window.resetRecognitionUrl, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
      }
    } catch (error) {
      console.error("Không thể làm mới nhận diện:", error);
    }
    clearCustomerForm();
    updateActiveCustomer(null);
    updateMatches([]);
    updatePurchaseHistory([]);
    showRecognitionAlert("Đang quét khuôn mặt...", "info");
    setWorkspaceLock(true);
    startRecognition(false);
  }

  function bindEvents() {
    if (startBtn) {
      startBtn.addEventListener("click", () => {
        showRecognitionAlert("Đang quét khuôn mặt...", "info");
        clearCustomerForm();
        updateActiveCustomer(null);
        updateMatches([]);
        updatePurchaseHistory([]);
        setWorkspaceLock(true);
        startRecognition(false);
      });
    }
    if (stopBtn) {
      stopBtn.addEventListener("click", () => stopRecognition(true));
    }
    window.addEventListener("beforeunload", () => stopRecognition(false));

    if (useBtn) {
      useBtn.addEventListener("click", async () => {
        if (!currentActiveCustomer || !currentActiveCustomer.id) return;
        populateCustomerForm(currentActiveCustomer);
        setWorkspaceLock(false);
        const { full_name: name, face_id: faceId } = currentActiveCustomer;
        const displayName = name ? name : faceId ? `Face ID ${faceId}` : "khách hàng";
        showRecognitionAlert(`Đang sử dụng thông tin ${displayName}.`, "success");
        await syncActiveCustomer(currentActiveCustomer.id);
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        stopRecognition(false);
        resetRecognition();
      });
    }
  }

  function setupTabs() {
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    if (!tabButtons.length) return;

    tabButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.dataset.tab;
        tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
        tabContents.forEach((panel) => {
          panel.classList.toggle("active", panel.id === targetId);
        });
      });
    });
  }

  function init() {
    setupTabs();

    if (!videoEl) {
      return;
    }

    bindEvents();
    updateMatches([]);
    const initialCustomer = window.initialActiveCustomer || null;
    const initialHistory = Array.isArray(window.initialPurchaseHistory)
      ? window.initialPurchaseHistory
      : [];

    if (initialCustomer && initialCustomer.id) {
      updateActiveCustomer(initialCustomer);
      populateCustomerForm(initialCustomer);
      updatePurchaseHistory(initialHistory);
      setWorkspaceLock(false);
      const faceSuffix = initialCustomer.face_id ? ` – Face ID ${initialCustomer.face_id}` : "";
      showRecognitionAlert(`Đang phục vụ ${initialCustomer.full_name || "khách hàng"}${faceSuffix}.`, "success");
      setStatus("Camera chưa bật.", "info");
    } else {
      updateActiveCustomer(null);
      updatePurchaseHistory([]);
      setWorkspaceLock(true);
      showRecognitionAlert("Chưa nhận diện khách hàng.", "info");
      startRecognition(true);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
