const direction = window.ATTENDANCE_DIRECTION || "in";
const directionLabel = window.ATTENDANCE_LABEL || "เข้า";
const liveBox = document.getElementById("live-box");
const recordsEl = document.getElementById("records");
const recordCountEl = document.getElementById("record-count");
const scanStatus = document.getElementById("scan-status");
const scanState = document.getElementById("scan-state");
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnOnce = document.getElementById("btn-once");

let timer = null;
let busy = false;

function setStatus(message, ok = true) {
  scanStatus.textContent = message || "";
  scanStatus.className = "status " + (ok ? "ok" : "err");
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatTime(iso) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("th-TH", { hour12: false });
  } catch {
    return iso;
  }
}

async function loadRecords() {
  const res = await fetch(`/api/attendance?direction=${encodeURIComponent(direction)}&limit=80`);
  const data = await res.json();
  if (!data.ok) {
    recordsEl.innerHTML = `<div class="empty">${escapeHtml(data.error || "โหลดไม่สำเร็จ")}</div>`;
    return;
  }
  recordCountEl.textContent = data.count ?? 0;
  if (!data.records || data.records.length === 0) {
    recordsEl.innerHTML = '<div class="empty">ยังไม่มีรายการวันนี้</div>';
    return;
  }
  recordsEl.innerHTML = data.records
    .map((r) => {
      const name = escapeHtml(r.display_name || r.person_id);
      const id = escapeHtml(r.person_id);
      const sim = r.similarity != null ? Number(r.similarity).toFixed(2) : "-";
      const t = escapeHtml(formatTime(r.timestamp_local || r.timestamp_utc));
      const img = r.snapshot_url
        ? `<img src="${escapeHtml(r.snapshot_url)}?t=${Date.now()}" alt="${name}" />`
        : '<div class="thumb-empty"></div>';
      return `
        <article class="record">
          ${img}
          <div class="meta">
            <strong>${name}</strong>
            <span>${t}</span>
            <span>${id} · sim ${sim}</span>
          </div>
        </article>`;
    })
    .join("");
}

async function scanOnce() {
  if (busy) return;
  busy = true;
  try {
    const res = await fetch(`/api/attendance/scan?direction=${encodeURIComponent(direction)}`, {
      method: "POST",
    });
    const contentType = res.headers.get("content-type") || "";
    if (!res.ok) {
      let err = "สแกนไม่สำเร็จ";
      if (contentType.includes("application/json")) {
        const data = await res.json();
        err = data.error || data.detail || err;
      }
      setStatus(err, false);
      return;
    }

    const marked = Number(res.headers.get("X-Marked-Count") || "0");
    const faces = Number(res.headers.get("X-Face-Count") || "0");
    const unknown = Number(res.headers.get("X-Unknown-Count") || "0");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    liveBox.innerHTML = `<img src="${url}" alt="attendance scan" />`;

    if (marked > 0) {
      setStatus(`ลงเวลา${directionLabel}สำเร็จ ${marked} คน · เจอใบหน้า ${faces}`);
    } else if (faces === 0) {
      setStatus("ไม่พบใบหน้าในเฟรม", false);
    } else if (unknown > 0 && marked === 0) {
      setStatus(`เจอใบหน้า ${faces} แต่ยังไม่รู้จักในระบบ`, false);
    } else {
      setStatus(`เจอใบหน้า ${faces} · ยังไม่มีรายการใหม่ (อาจติด cooldown)`);
    }
    await loadRecords();
  } catch (err) {
    setStatus(String(err), false);
  } finally {
    busy = false;
  }
}

function startScan() {
  if (timer) return;
  scanState.textContent = "กำลังสแกน...";
  setStatus(`เริ่มลงเวลา${directionLabel}`);
  scanOnce();
  timer = setInterval(scanOnce, 2500);
}

function stopScan() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  scanState.textContent = "หยุดอยู่";
  setStatus("หยุดสแกนแล้ว");
}

btnStart.addEventListener("click", startScan);
btnStop.addEventListener("click", stopScan);
btnOnce.addEventListener("click", scanOnce);
window.addEventListener("beforeunload", stopScan);

loadRecords().catch((err) => setStatus(String(err), false));
