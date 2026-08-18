const filterForm = document.getElementById("filter-form");
const studentsEl = document.getElementById("students");
const studentCountEl = document.getElementById("student-count");
const filterStatus = document.getElementById("filter-status");
const historyModal = document.getElementById("history-modal");
const historyProfile = document.getElementById("history-profile");
const historyRecords = document.getElementById("history-records");

let schoolOptions = null;

function setStatus(message, ok = true) {
  filterStatus.textContent = message || "";
  filterStatus.className = "status " + (ok ? "ok" : "err");
}

function escapeHtml(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadFilterOptions() {
  schoolOptions = await SchoolFields.loadOptions();
  SchoolFields.fillSelect(document.getElementById("f_year"), schoolOptions.academic_year, {
    emptyLabel: "ทุกปีการศึกษา",
    addValue: SchoolFields.ADD_YEAR,
    addLabel: "+ เพิ่มปีการศึกษา",
  });
  SchoolFields.fillSelect(document.getElementById("f_term"), schoolOptions.term, {
    emptyLabel: "ทุกเทอม",
  });
  SchoolFields.fillSelect(document.getElementById("f_grade"), schoolOptions.grade, {
    emptyLabel: "ทุกชั้น",
  });
  SchoolFields.fillSelect(document.getElementById("f_room"), schoolOptions.room, {
    emptyLabel: "ทุกห้อง",
    addValue: SchoolFields.ADD_ROOM,
    addLabel: "+ เพิ่มห้อง",
  });

  const yearEl = document.getElementById("f_year");
  const roomEl = document.getElementById("f_room");
  yearEl.onchange = async () => {
    if (yearEl.value !== SchoolFields.ADD_YEAR) return;
    const value = prompt("เพิ่มปีการศึกษา (พ.ศ. 4 หลัก เช่น 2569)");
    yearEl.value = "";
    if (!value) return;
    const res = await fetch("/api/school-options/academic-year", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "เพิ่มปีการศึกษาไม่สำเร็จ");
      return;
    }
    schoolOptions = data.options;
    await loadFilterOptions();
    yearEl.value = value.trim();
  };
  roomEl.onchange = async () => {
    if (roomEl.value !== SchoolFields.ADD_ROOM) return;
    const value = prompt("เพิ่มห้อง เช่น 1 หรือ ห้องพิเศษ");
    roomEl.value = "";
    if (!value) return;
    const res = await fetch("/api/school-options/room", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "เพิ่มห้องไม่สำเร็จ");
      return;
    }
    schoolOptions = data.options;
    await loadFilterOptions();
    roomEl.value = value.trim();
  };
}

function filtersQuery() {
  const params = new URLSearchParams();
  const year = document.getElementById("f_year").value.trim();
  const term = document.getElementById("f_term").value.trim();
  const grade = document.getElementById("f_grade").value.trim();
  const room = document.getElementById("f_room").value.trim();
  const q = document.getElementById("f_q").value.trim();
  if (year) params.set("academic_year", year);
  if (term) params.set("term", term);
  if (grade) params.set("grade", grade);
  if (room) params.set("room", room);
  if (q) params.set("q", q);
  return params;
}

async function loadStudents() {
  const params = filtersQuery();
  const res = await fetch(`/api/students?${params.toString()}`);
  const data = await res.json();
  if (!data.ok) {
    setStatus(data.error || "โหลดไม่สำเร็จ", false);
    return;
  }
  studentCountEl.textContent = data.count ?? 0;
  if (!data.students || data.students.length === 0) {
    studentsEl.innerHTML = '<div class="empty">ไม่พบนักเรียนตามเงื่อนไข</div>';
    setStatus("ไม่พบข้อมูล");
    return;
  }
  studentsEl.innerHTML = `
    <table class="students-table">
      <thead>
        <tr>
          <th></th>
          <th>ชื่อ</th>
          <th>รหัส</th>
          <th>ปีการศึกษา</th>
          <th>เทอม</th>
          <th>ชั้น</th>
          <th>ห้อง</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${data.students
          .map((s) => {
            const name = escapeHtml(s.display_name || s.person_id);
            const id = escapeHtml(s.person_id);
            const src = s.preview_url ? `${s.preview_url}?t=${Date.now()}` : "";
            return `<tr>
              <td><img class="table-avatar" src="${src}" alt="${name}" /></td>
              <td><strong>${name}</strong></td>
              <td>${id}</td>
              <td>${escapeHtml(s.academic_year || "-")}</td>
              <td>${escapeHtml(s.term || "-")}</td>
              <td>${escapeHtml(s.grade || "-")}</td>
              <td>${escapeHtml(s.room || "-")}</td>
              <td><button type="button" class="btn-secondary btn-small" data-history="${id}">ดูประวัติ</button></td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
  setStatus(`พบ ${data.count} คน`);
}

function formatTime(iso) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("th-TH", { hour12: false });
  } catch {
    return iso;
  }
}

async function openHistory(personId) {
  const res = await fetch(`/api/students/${encodeURIComponent(personId)}/history`);
  const data = await res.json();
  if (!data.ok) {
    setStatus(data.error || "โหลดประวัติไม่สำเร็จ", false);
    return;
  }
  const s = data.student;
  historyProfile.innerHTML = `
    <img src="${escapeHtml(s.preview_url)}?t=${Date.now()}" alt="" />
    <div>
      <strong>${escapeHtml(s.display_name || s.person_id)}</strong>
      <div>${escapeHtml(s.person_id)}</div>
      <div>ปีการศึกษา ${escapeHtml(s.academic_year || "-")} · เทอม ${escapeHtml(s.term || "-")}</div>
      <div>ชั้น ${escapeHtml(s.grade || "-")} / ห้อง ${escapeHtml(s.room || "-")}</div>
    </div>`;

  if (!data.records || data.records.length === 0) {
    historyRecords.innerHTML = '<div class="empty">ยังไม่มีประวัติเข้า-ออก</div>';
  } else {
    historyRecords.innerHTML = data.records
      .map((r) => {
        const dir = r.direction === "out" ? "ออก" : "เข้า";
        const img = r.snapshot_url
          ? `<img src="${escapeHtml(r.snapshot_url)}" alt="" />`
          : '<div class="thumb-empty"></div>';
        return `<article class="record">
          ${img}
          <div class="meta">
            <strong>${dir}</strong>
            <span>${escapeHtml(formatTime(r.timestamp_local || r.timestamp_utc))}</span>
            <span>sim ${r.similarity != null ? Number(r.similarity).toFixed(2) : "-"}</span>
          </div>
        </article>`;
      })
      .join("");
  }
  historyModal.classList.remove("hidden");
  historyModal.setAttribute("aria-hidden", "false");
}

function closeHistory() {
  historyModal.classList.add("hidden");
  historyModal.setAttribute("aria-hidden", "true");
}

filterForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadStudents();
});

document.getElementById("btn-reset").addEventListener("click", async () => {
  document.getElementById("f_q").value = "";
  await loadFilterOptions();
  await loadStudents();
});

studentsEl.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-history]");
  if (!btn) return;
  await openHistory(btn.getAttribute("data-history"));
});

historyModal.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-history]")) closeHistory();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !historyModal.classList.contains("hidden")) {
    closeHistory();
  }
});

Promise.all([loadFilterOptions(), loadStudents()]).catch((err) => setStatus(String(err), false));
