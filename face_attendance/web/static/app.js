const statusEl = document.getElementById("status");
const peopleEl = document.getElementById("people");
const countEl = document.getElementById("count");
const previewBox = document.getElementById("preview-box");
const form = document.getElementById("enroll-form");

function setStatus(message, ok = true) {
  statusEl.textContent = message || "";
  statusEl.className = "status " + (ok ? "ok" : "err");
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
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
        <article class="person">
          <img src="${src}" alt="${name}" />
          <div class="meta">
            <strong>${name}</strong>
            <span>${id} · score ${score}</span>
          </div>
          <button class="btn-danger" data-del="${id}">ลบ</button>
        </article>`;
    })
    .join("");
}

peopleEl.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-del]");
  if (!btn) return;
  const id = btn.getAttribute("data-del");
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
