const statusEl = document.getElementById("status");
const peopleEl = document.getElementById("people");
const countEl = document.getElementById("count");
const previewBox = document.getElementById("preview-box");
const form = document.getElementById("enroll-form");
const editModal = document.getElementById("edit-modal");
const editForm = document.getElementById("edit-form");
const editStatus = document.getElementById("edit-status");
const editPersonId = document.getElementById("edit_person_id");
const editDisplayName = document.getElementById("edit_display_name");
const editImage = document.getElementById("edit_image");
const editPreviewImg = document.getElementById("edit_preview_img");

if (!form || !peopleEl) {
  // หน้าอื่นที่ไม่ใช่ลงทะเบียน
} else {
  bootEnrollPage();
}

function bootEnrollPage() {
function setStatus(message, ok = true) {
  statusEl.textContent = message || "";
  statusEl.className = "status " + (ok ? "ok" : "err");
}

function setEditStatus(message, ok = true) {
  editStatus.textContent = message || "";
  editStatus.className = "status " + (ok ? "ok" : "err");
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function closeMenus(except = null) {
  peopleEl.querySelectorAll(".menu.open").forEach((menu) => {
    if (menu !== except) menu.classList.remove("open");
  });
}

async function loadPeople() {
  const res = await fetch("/api/people");
  const data = await res.json();
  countEl.textContent = data.count ?? 0;
  if (!data.people || data.people.length === 0) {
    peopleEl.innerHTML = '<div class="empty">ยังไม่มีรายชื่อ — เริ่มลงทะเบียนทางซ้าย</div>';
    return;
  }
  peopleEl.innerHTML = data.people
    .map((p) => {
      const name = escapeHtml(p.display_name || p.person_id);
      const id = escapeHtml(p.person_id);
      const score = p.face_score != null ? Number(p.face_score).toFixed(2) : "-";
      const src = p.preview_url ? `${p.preview_url}?t=${Date.now()}` : "";
      return `
        <article class="person" data-id="${id}">
          <img src="${src}" alt="${name}" />
          <div class="meta">
            <strong>${name}</strong>
            <span>${id} · score ${score}</span>
          </div>
          <div class="menu">
            <button type="button" class="menu-toggle" data-menu-toggle aria-haspopup="true">จัดการ</button>
            <div class="menu-panel" role="menu">
              <button type="button" class="menu-item" data-edit="${id}" role="menuitem">แก้ไข</button>
              <button type="button" class="menu-item danger" data-del="${id}" role="menuitem">ลบ</button>
            </div>
          </div>
        </article>`;
    })
    .join("");
}

function openEditModal(person) {
  editPersonId.value = person.person_id;
  editDisplayName.value = person.display_name || person.person_id;
  editImage.value = "";
  editPreviewImg.src = person.preview_url
    ? `${person.preview_url}?t=${Date.now()}`
    : "";
  setEditStatus("");
  editModal.classList.remove("hidden");
  editModal.setAttribute("aria-hidden", "false");
  editDisplayName.focus();
}

function closeEditModal() {
  editModal.classList.add("hidden");
  editModal.setAttribute("aria-hidden", "true");
  setEditStatus("");
}

peopleEl.addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-menu-toggle]");
  if (toggle) {
    const menu = toggle.closest(".menu");
    const willOpen = !menu.classList.contains("open");
    closeMenus();
    if (willOpen) menu.classList.add("open");
    return;
  }

  const editBtn = event.target.closest("[data-edit]");
  if (editBtn) {
    closeMenus();
    const id = editBtn.getAttribute("data-edit");
    const res = await fetch(`/api/people/${encodeURIComponent(id)}`);
    const data = await res.json();
    if (!data.ok) {
      setStatus(data.error || "โหลดข้อมูลไม่สำเร็จ", false);
      return;
    }
    openEditModal(data.person);
    return;
  }

  const delBtn = event.target.closest("[data-del]");
  if (!delBtn) return;
  closeMenus();
  const id = delBtn.getAttribute("data-del");
  if (!confirm(`ลบ ${id} ออกจากระบบ?`)) return;
  const res = await fetch(`/api/people/${encodeURIComponent(id)}`, { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    setStatus(data.detail || "ลบไม่สำเร็จ", false);
    return;
  }
  setStatus(`ลบ ${id} แล้ว`);
  await loadPeople();
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".menu")) closeMenus();
});

editModal.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-modal]")) closeEditModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !editModal.classList.contains("hidden")) {
    closeEditModal();
  }
});

editForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = editPersonId.value.trim();
  const body = new FormData();
  body.append("display_name", editDisplayName.value.trim());
  if (editImage.files && editImage.files[0]) {
    body.append("image", editImage.files[0]);
  }
  setEditStatus("กำลังบันทึก...");
  const res = await fetch(`/api/people/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body,
  });
  const data = await res.json();
  if (!data.ok) {
    setEditStatus(data.error || "แก้ไขไม่สำเร็จ", false);
    return;
  }
  setStatus(`แก้ไข ${data.person.person_id} แล้ว`);
  closeEditModal();
  await loadPeople();
});

document.getElementById("btn-edit-camera").addEventListener("click", async () => {
  const id = editPersonId.value.trim();
  const body = new FormData();
  body.append("display_name", editDisplayName.value.trim());
  body.append("from_camera", "1");
  setEditStatus("กำลังอัปเดตรูปจากกล้อง...");
  const res = await fetch(`/api/people/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body,
  });
  const data = await res.json();
  if (!data.ok) {
    setEditStatus(data.error || "อัปเดตรูปจากกล้องไม่สำเร็จ", false);
    return;
  }
  setStatus(`อัปเดตรูป ${data.person.person_id} จากกล้องแล้ว`);
  closeEditModal();
  await loadPeople();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const personId = document.getElementById("person_id").value.trim();
  const displayName = document.getElementById("display_name").value.trim();
  const fileInput = document.getElementById("image");
  if (!fileInput.files || !fileInput.files[0]) {
    setStatus("เลือกไฟล์รูป หรือใช้ปุ่มถ่ายจากกล้อง", false);
    return;
  }
  const body = new FormData();
  body.append("person_id", personId);
  body.append("display_name", displayName);
  body.append("image", fileInput.files[0]);
  setStatus("กำลังบันทึก...");
  const res = await fetch("/api/enroll", { method: "POST", body });
  const data = await res.json();
  if (!data.ok) {
    setStatus(data.error || "บันทึกไม่สำเร็จ", false);
    return;
  }
  setStatus(`ลงทะเบียน ${data.person.person_id} สำเร็จ`);
  form.reset();
  await loadPeople();
});

document.getElementById("btn-camera").addEventListener("click", async () => {
  const personId = document.getElementById("person_id").value.trim();
  const displayName = document.getElementById("display_name").value.trim();
  if (!personId) {
    setStatus("กรอกรหัสนักเรียนก่อน", false);
    return;
  }
  const body = new FormData();
  body.append("person_id", personId);
  body.append("display_name", displayName);
  setStatus("กำลังถ่ายจากกล้อง...");
  const res = await fetch("/api/enroll/from-camera", { method: "POST", body });
  const data = await res.json();
  if (!data.ok) {
    setStatus(data.error || "ถ่ายจากกล้องไม่สำเร็จ", false);
    return;
  }
  setStatus(`ลงทะเบียนจากกล้อง: ${data.person.person_id}`);
  await loadPeople();
  await refreshCameraPreview();
});

async function refreshCameraPreview() {
  setStatus("กำลังดึงภาพกล้อง...");
  const url = `/api/camera/snapshot?t=${Date.now()}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    setStatus(err.detail || "ดึงภาพกล้องไม่สำเร็จ", false);
    return;
  }
  const blob = await res.blob();
  const faceCount = res.headers.get("X-Face-Count") || "?";
  const imgUrl = URL.createObjectURL(blob);
  previewBox.innerHTML = `<img src="${imgUrl}" alt="camera snapshot" />`;
  setStatus(`ดึงภาพกล้องสำเร็จ · ตรวจพบใบหน้า ${faceCount} คน`);
}

document.getElementById("btn-preview").addEventListener("click", refreshCameraPreview);

loadPeople().catch((err) => setStatus(String(err), false));
}
