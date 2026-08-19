const PAGE = document.body.dataset.page;
const THAI_MONTHS = [
  "มกราคม",
  "กุมภาพันธ์",
  "มีนาคม",
  "เมษายน",
  "พฤษภาคม",
  "มิถุนายน",
  "กรกฎาคม",
  "สิงหาคม",
  "กันยายน",
  "ตุลาคม",
  "พฤศจิกายน",
  "ธันวาคม",
];

const state = {
  user: null,
  tab: "entry",
  cursor: new Date(),
  branches: [],
  groups: [],
};

function $(sel, root = document) {
  return root.querySelector(sel);
}

function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content;
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function monthLabel(d) {
  return `${THAI_MONTHS[d.getMonth()]} ${d.getFullYear() + 543}`;
}

function toast(msg, error = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("error", !!error);
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 2600);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...opts,
    headers: {
      ...(opts.body && !(opts.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(opts.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || "เกิดข้อผิดพลาด");
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function icon(name) {
  const paths = {
    package: '<path d="M16.5 9.4 7.55 4.24"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.29 7 12 12l8.71-5"/><path d="M12 22V12"/>',
    list: '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    bar: '<path d="M3 3v18h18"/><path d="M7 16V8"/><path d="M12 16V4"/><path d="M17 16v-6"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    report: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    store: '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M22 7v3a2 2 0 0 1-2 2 2.83 2.83 0 0 1-2-1 2.83 2.83 0 0 1-4 0 2.83 2.83 0 0 1-4 0 2.83 2.83 0 0 1-2 1 2 2 0 0 1-2-2V7"/>',
    line: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    left: '<polyline points="15 18 9 12 15 6"/>',
    right: '<polyline points="9 18 15 12 9 6"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  };
  return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[name] || ""}</svg>`;
}

function fmtNum(n, digits) {
  const v = Number(n) || 0;
  return v.toLocaleString("th-TH", digits != null ? { minimumFractionDigits: digits, maximumFractionDigits: digits } : undefined);
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("th-TH");
}

function root() {
  return $("#root");
}

/* ---------------- login ---------------- */
function renderLogin(mode = "signin") {
  root().innerHTML = "";
  root().append(
    h(`<div class="center-wrap">
      <div class="card auth-card">
        <div class="card-body">
          <img class="logo" src="/static/logo.png" alt="Saint Martin" />
          <h1>${mode === "forgot" ? "ลืมรหัสผ่าน" : "เข้าสู่ระบบ"}</h1>
          <p class="auth-sub">📦 ระบบบันทึกรับของบริจาค 7-Eleven</p>
          <form id="auth-form">
            <div class="field">
              <label>อีเมล</label>
              <input class="input" name="email" type="email" required />
            </div>
            ${
              mode === "signin"
                ? `<div class="field"><label>รหัสผ่าน</label><input class="input" name="password" type="password" required /></div>`
                : ""
            }
            <button class="btn btn-full" type="submit" id="auth-submit">${
              mode === "forgot" ? "ส่งลิงก์รีเซ็ต" : "เข้าสู่ระบบ"
            }</button>
          </form>
          <p style="margin:.9rem 0 0;text-align:center">
            ${
              mode === "signin"
                ? `<button class="link" id="to-forgot">ลืมรหัสผ่าน?</button>`
                : `<button class="link" id="to-signin">← กลับไปเข้าสู่ระบบ</button>`
            }
          </p>
        </div>
      </div>
    </div>`)
  );
  $("#auth-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const btn = $("#auth-submit");
    btn.disabled = true;
    btn.textContent = "กำลังดำเนินการ...";
    try {
      if (mode === "signin") {
        const email = fd.get("email");
        const password = fd.get("password");
        if (!email) throw new Error("กรุณากรอกอีเมล");
        if (!password) throw new Error("กรุณากรอกรหัสผ่าน");
        await api("/api/login", { method: "POST", body: JSON.stringify({ email, password }) });
        toast("เข้าสู่ระบบสำเร็จ");
        await bootDashboard();
      } else {
        const email = fd.get("email");
        if (!email) throw new Error("กรุณากรอกอีเมล");
        await api("/api/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
        toast("ส่งลิงก์รีเซ็ตรหัสผ่านไปยังอีเมลแล้ว");
      }
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
      btn.textContent = mode === "forgot" ? "ส่งลิงก์รีเซ็ต" : "เข้าสู่ระบบ";
    }
  };
  const tog = $("#to-forgot") || $("#to-signin");
  if (tog) tog.onclick = () => renderLogin(mode === "signin" ? "forgot" : "signin");
}

function renderReset() {
  const token = new URLSearchParams(location.search).get("token") || "";
  root().innerHTML = "";
  if (!token) {
    root().append(
      h(`<div class="center-wrap"><div class="card auth-card"><div class="card-body">
        <p class="muted">กำลังตรวจสอบลิงก์รีเซ็ต... หากไม่ตอบสนอง กรุณาคลิกลิงก์จากอีเมลอีกครั้ง</p>
      </div></div></div>`)
    );
    return;
  }
  root().append(
    h(`<div class="center-wrap"><div class="card auth-card"><div class="card-body">
      <img class="logo" src="/static/logo.png" alt="Saint Martin" />
      <h1>ตั้งรหัสผ่านใหม่</h1>
      <p class="auth-sub">กรอกรหัสผ่านใหม่เพื่อเข้าสู่ระบบ</p>
      <form id="reset-form">
        <div class="field"><label>รหัสผ่านใหม่</label><input class="input" name="password" type="password" minlength="6" required /></div>
        <div class="field"><label>ยืนยันรหัสผ่าน</label><input class="input" name="confirm" type="password" minlength="6" required /></div>
        <button class="btn btn-full" type="submit">บันทึกรหัสผ่านใหม่</button>
      </form>
    </div></div></div>`)
  );
  $("#reset-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password: fd.get("password"), confirm: fd.get("confirm") }),
      });
      toast("ตั้งรหัสผ่านใหม่สำเร็จ");
      history.replaceState({}, "", "/");
      renderLogin();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

/* ---------------- public donate ---------------- */
function renderDonate() {
  const params = new URLSearchParams(location.search);
  const preset = params.get("code") || "";
  let confirmed = null;
  let contacts = [];

  const paintGate = (err = "") => {
    root().innerHTML = "";
    root().append(
      h(`<div class="center-wrap"><div class="card auth-card"><div class="card-body">
        <img class="logo" src="/static/logo.png" alt="Saint Martin" />
        <h1>ยืนยันสาขา</h1>
        <p class="auth-sub">กรุณากรอกรหัสสาขาของคุณเพื่อเข้าสู่แบบฟอร์ม</p>
        <form id="gate">
          <div class="field"><label>รหัสสาขา</label><input class="input" name="code" value="${preset}" placeholder="เช่น 15005" required /></div>
          <p class="muted" id="gate-err" style="color:hsl(var(--destructive))">${err}</p>
          <button class="btn btn-full" type="submit">เข้าสู่แบบฟอร์ม</button>
        </form>
      </div></div></div>`)
    );
    $("#gate").onsubmit = async (e) => {
      e.preventDefault();
      const code = new FormData(e.target).get("code");
      try {
        const data = await api(`/api/public/branch?code=${encodeURIComponent(code)}`);
        confirmed = data.branch;
        contacts = data.contacts || [];
        paintForm();
      } catch (err) {
        paintGate(err.message);
      }
    };
  };

  const paintSuccess = () => {
    root().innerHTML = "";
    root().append(
      h(`<div class="center-wrap"><div class="card auth-card"><div class="card-body success-box">
        <h2>บันทึกสำเร็จ!</h2>
        <p>ข้อมูลการรับของบริจาคถูกบันทึกเรียบร้อยแล้ว</p>
        <button class="btn" id="again">บันทึกรายการใหม่</button>
      </div></div></div>`)
    );
    $("#again").onclick = () => paintForm();
  };

  const paintForm = () => {
    const c0 = contacts[0] || {};
    const names = [...new Set(contacts.map((c) => c.contact_name).filter(Boolean))];
    const positions = [...new Set(contacts.map((c) => c.position).filter(Boolean))];
    root().innerHTML = "";
    root().append(
      h(`<div class="center-wrap" style="align-items:flex-start;padding-top:2rem">
        <div class="card" style="width:100%;max-width:32rem">
          <div class="card-body">
            <h1 style="text-align:center;margin-top:0">แบบฟอร์มบันทึกรับของบริจาค</h1>
            <p class="auth-sub">${confirmed.code} — ${confirmed.name}</p>
            ${donationFormHtml({
              date: todayISO(),
              contact: c0.contact_name || "",
              position: c0.position || "",
              phone: c0.phone || "",
              names,
              positions,
              publicMode: true,
            })}
          </div>
        </div>
      </div>`)
    );
    wireDonationForm($("form[data-donation]"), {
      getBranch: () => confirmed,
      onSuccess: paintSuccess,
      publicMode: true,
    });
  };

  if (preset) {
    api(`/api/public/branch?code=${encodeURIComponent(preset)}`)
      .then((data) => {
        confirmed = data.branch;
        contacts = data.contacts || [];
        paintForm();
      })
      .catch(() => paintGate());
  } else {
    paintGate();
  }
}

function donationFormHtml(opts) {
  const names = opts.names || [];
  const positions = opts.positions || [];
  return `<form data-donation>
    <div class="form-grid">
      <div class="field"><label>วันที่</label><input class="input" name="date" type="date" value="${opts.date || todayISO()}" required /></div>
      ${
        opts.publicMode
          ? ""
          : `<div class="field combo span-2" id="branch-combo">
              <label>สาขา</label>
              <input class="input" name="branchSearch" placeholder="พิมพ์รหัสหรือชื่อสาขา..." autocomplete="off" />
              <input type="hidden" name="branchCode" />
              <div class="combo-list hidden"></div>
            </div>`
      }
      <div class="field"><label>จำนวนชิ้น *</label><input class="input" name="pieces" type="number" min="1" required /></div>
      <div class="field"><label>จำนวนตะกร้า</label><input class="input" name="baskets" type="number" min="0" /></div>
      <div class="field"><label>ชื่อผู้ติดต่อ</label>
        <input class="input" name="contactName" list="contact-names" placeholder="พิมพ์หรือเลือกชื่อ..." value="${opts.contact || ""}" />
        <datalist id="contact-names">${names.map((n) => `<option value="${n}"></option>`).join("")}</datalist>
      </div>
      <div class="field"><label>ตำแหน่ง</label>
        <input class="input" name="position" list="positions" placeholder="พิมพ์หรือเลือกตำแหน่ง..." value="${opts.position || ""}" />
        <datalist id="positions">${positions.map((n) => `<option value="${n}"></option>`).join("")}</datalist>
      </div>
      <div class="field"><label>เบอร์โทร</label><input class="input" name="phone" value="${opts.phone || ""}" /></div>
      <div class="field"><label>น้ำหนักรวม (กก.)</label><input class="input" name="weightKg" type="number" min="0" step="0.01" /></div>
      <div class="field span-2"><label>รูปภาพ</label>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <label class="btn btn-outline btn-sm">เลือกรูป<input type="file" name="photos" accept="image/*" multiple hidden /></label>
          <label class="btn btn-outline btn-sm">ถ่ายรูป<input type="file" name="camera" accept="image/*" capture="environment" hidden /></label>
        </div>
        <div class="photos" data-previews></div>
      </div>
    </div>
    <button class="btn btn-full" type="submit" style="margin-top:1rem">บันทึก</button>
  </form>`;
}

function wireDonationForm(form, { getBranch, onSuccess, publicMode }) {
  const previews = $("[data-previews]", form);
  const filesHeld = [];
  const addFiles = (list) => {
    for (const f of list) filesHeld.push(f);
    previews.innerHTML = "";
    filesHeld.forEach((f) => {
      const img = document.createElement("img");
      img.src = URL.createObjectURL(f);
      previews.append(img);
    });
  };
  form.querySelectorAll('input[type=file]').forEach((inp) => {
    inp.onchange = () => addFiles(inp.files);
  });

  if (!publicMode) {
    const combo = $("#branch-combo", form);
    const input = combo.querySelector('input[name="branchSearch"]');
    const hidden = combo.querySelector('input[name="branchCode"]');
    const list = $(".combo-list", combo);
    const renderList = (q) => {
      const n = (q || "").toLowerCase().trim();
      const items = state.branches.filter(
        (b) => !n || b.name.toLowerCase().includes(n) || b.code.includes(n)
      );
      if (!items.length) {
        list.innerHTML = `<div class="combo-item">ไม่พบสาขา</div>`;
      } else {
        list.innerHTML = items
          .slice(0, 40)
          .map((b) => `<button type="button" class="combo-item" data-code="${b.code}">${b.code} — ${b.name}</button>`)
          .join("");
        list.querySelectorAll(".combo-item[data-code]").forEach((btn) => {
          btn.onclick = async () => {
            hidden.value = btn.dataset.code;
            const b = state.branches.find((x) => x.code === btn.dataset.code);
            input.value = `${b.code} — ${b.name}`;
            list.classList.add("hidden");
            try {
              const data = await api(`/api/public/branch?code=${encodeURIComponent(b.code)}`);
              const c = (data.contacts || [])[0] || {};
              if (c.contact_name) form.contactName.value = c.contact_name;
              if (c.position) form.position.value = c.position;
              if (c.phone) form.phone.value = c.phone;
            } catch (_) {
              /* ignore */
            }
          };
        });
      }
      list.classList.remove("hidden");
    };
    input.onfocus = () => renderList(input.value);
    input.oninput = () => {
      hidden.value = "";
      renderList(input.value);
    };
    document.addEventListener("click", (e) => {
      if (!combo.contains(e.target)) list.classList.add("hidden");
    });
  }

  form.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const branch = publicMode ? getBranch() : state.branches.find((b) => b.code === fd.get("branchCode"));
    if (!branch || !fd.get("pieces")) {
      toast("กรุณากรอกข้อมูลให้ครบ", true);
      return;
    }
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.textContent = "กำลังบันทึก...";
    try {
      const body = new FormData();
      body.set("date", fd.get("date"));
      body.set("branchCode", branch.code);
      body.set("pieces", fd.get("pieces"));
      body.set("baskets", fd.get("baskets") || "");
      body.set("contactName", fd.get("contactName") || "");
      body.set("position", fd.get("position") || "");
      body.set("phone", fd.get("phone") || "");
      body.set("weightKg", fd.get("weightKg") || "0");
      filesHeld.forEach((f) => body.append("photos", f));
      const url = publicMode ? "/api/public/donations" : "/api/donations";
      await api(url, { method: "POST", body });
      toast("บันทึกสำเร็จ");
      form.reset();
      previews.innerHTML = "";
      filesHeld.length = 0;
      if (form.date) form.date.value = todayISO();
      if (onSuccess) onSuccess();
      if (!publicMode) loadMonthSummary();
    } catch (err) {
      toast(err.message || "บันทึกไม่สำเร็จ กรุณาลองใหม่", true);
    } finally {
      btn.disabled = false;
      btn.textContent = "บันทึก";
    }
  };
}

/* ---------------- dashboard ---------------- */
function dashboardShell() {
  root().innerHTML = "";
  root().append(
    h(`<div>
      <header class="header">
        <div class="container">
          <div class="header-row">
            <h1>📦 ระบบบันทึกรับของบริจาค 7-Eleven</h1>
            <div class="header-actions">
              <button class="btn btn-outline btn-sm" id="copy-link">${icon("link")}<span class="hide-sm">ลิงก์สาขา</span></button>
              <div class="month-nav" id="month-nav">
                <button class="btn btn-outline btn-icon" id="prev-m">${icon("left")}</button>
                <span id="month-label"></span>
                <button class="btn btn-outline btn-icon" id="next-m">${icon("right")}</button>
              </div>
              <button class="btn btn-ghost btn-icon" id="logout" title="ออกจากระบบ">${icon("logout")}</button>
            </div>
          </div>
          <div class="tabs">
            <button class="tab active" data-tab="entry">${icon("package")}บันทึกข้อมูล</button>
            <button class="tab" data-tab="list">${icon("list")}รายการของที่รับบริจาค</button>
            <button class="tab" data-tab="branchReport">${icon("bar")}สรุปตามสาขา</button>
            <button class="tab" data-tab="groups">${icon("users")}กลุ่มรับของ</button>
            <button class="tab" data-tab="report">${icon("report")}รายงานตามกลุ่ม</button>
            <button class="tab" data-tab="master">${icon("store")}ข้อมูลสาขา</button>
            <button class="tab" data-tab="line">${icon("line")}LINE</button>
          </div>
        </div>
      </header>
      <main class="container main" id="main"></main>
    </div>`)
  );
  $("#month-label").textContent = monthLabel(state.cursor);
  $("#copy-link").onclick = async () => {
    const url = `${location.origin}/donate`;
    await navigator.clipboard.writeText(url);
    toast("คัดลอกลิงก์แล้ว: " + url);
  };
  $("#logout").onclick = async () => {
    await api("/api/logout", { method: "POST", body: "{}" });
    toast("ออกจากระบบแล้ว");
    state.user = null;
    renderLogin();
  };
  $("#prev-m").onclick = () => {
    state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() - 1, 1);
    $("#month-label").textContent = monthLabel(state.cursor);
    if (state.tab === "entry") loadMonthSummary();
    if (state.tab === "branchReport") renderBranchReport();
  };
  $("#next-m").onclick = () => {
    state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() + 1, 1);
    $("#month-label").textContent = monthLabel(state.cursor);
    if (state.tab === "entry") loadMonthSummary();
    if (state.tab === "branchReport") renderBranchReport();
  };
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });
}

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $("#month-nav").style.display = tab === "entry" || tab === "branchReport" ? "flex" : "none";
  const renderers = {
    entry: renderEntry,
    list: renderList,
    branchReport: renderBranchReport,
    groups: renderGroups,
    report: renderGroupReport,
    master: renderMaster,
    line: renderLine,
  };
  (renderers[tab] || renderEntry)();
}

async function loadMonthSummary() {
  const y = state.cursor.getFullYear();
  const m = state.cursor.getMonth() + 1;
  const data = await api(`/api/donations/month-summary?year=${y}&month=${m}`);
  const el = $("#month-summary");
  if (!el) return;
  const t = data.totals;
  el.innerHTML = `
    <h2 class="muted" style="font-size:1.1rem;font-weight:600">สรุปประจำเดือน ${data.label}</h2>
    <div class="grid-3">
      <div class="card stat"><div class="stat-icon">📥</div><div><p class="muted">จำนวนครั้งที่รับ</p><p class="stat-value">${fmtNum(t.totalRecords)} ครั้ง</p></div></div>
      <div class="card stat"><div class="stat-icon">📦</div><div><p class="muted">จำนวนชิ้นรวม</p><p class="stat-value">${fmtNum(t.totalPieces)} ชิ้น</p></div></div>
      <div class="card stat"><div class="stat-icon">⚖️</div><div><p class="muted">น้ำหนักรวม</p><p class="stat-value">${fmtNum(t.totalWeight, 2)} กก.</p></div></div>
    </div>`;
}

async function renderEntry() {
  const main = $("#main");
  main.innerHTML = `<div class="space-y">
    <div id="month-summary"></div>
    <div class="card"><div class="card-body">
      <h2 style="margin-top:0">บันทึกรับของบริจาค</h2>
      ${donationFormHtml({})}
    </div></div>
  </div>`;
  wireDonationForm($("form[data-donation]"), { publicMode: false });
  await loadMonthSummary();
}

function filterBar(idPrefix) {
  const d = todayISO();
  return `<div class="toolbar" data-filter="${idPrefix}">
    <div class="field"><label>ช่วง</label>
      <select class="select" data-mode>
        <option value="day">วัน</option>
        <option value="range">ช่วงวัน</option>
        <option value="month">เดือน</option>
      </select>
    </div>
    <div class="field" data-f="day"><label>วันที่</label><input class="input" type="date" data-date value="${d}" /></div>
    <div class="field hidden" data-f="range"><label>ตั้งแต่</label><input class="input" type="date" data-start value="${d}" /></div>
    <div class="field hidden" data-f="range"><label>ถึง</label><input class="input" type="date" data-end value="${d}" /></div>
    <div class="field hidden" data-f="month"><label>เดือน</label>
      <select class="select" data-month>${THAI_MONTHS.map((n, i) => `<option value="${i + 1}" ${i === new Date().getMonth() ? "selected" : ""}>${n}</option>`).join("")}</select>
    </div>
    <div class="field hidden" data-f="month"><label>ปี (พ.ศ.)</label>
      <input class="input" type="number" data-year value="${new Date().getFullYear() + 543}" />
    </div>
  </div>`;
}

function wireFilter(rootEl, onChange) {
  const mode = $("[data-mode]", rootEl);
  const sync = () => {
    const m = mode.value;
    rootEl.querySelectorAll("[data-f]").forEach((el) => {
      el.classList.toggle("hidden", el.dataset.f !== m);
    });
    onChange(filterQuery(rootEl));
  };
  rootEl.querySelectorAll("input,select").forEach((el) => {
    el.onchange = sync;
  });
  sync();
}

function filterQuery(rootEl) {
  const mode = $("[data-mode]", rootEl).value;
  const q = new URLSearchParams({ mode });
  if (mode === "day") q.set("date", $("[data-date]", rootEl).value);
  if (mode === "range") {
    q.set("start", $("[data-start]", rootEl).value);
    q.set("end", $("[data-end]", rootEl).value);
  }
  if (mode === "month") {
    q.set("month", $("[data-month]", rootEl).value);
    q.set("year", Number($("[data-year]", rootEl).value) - 543);
  }
  return q;
}

async function renderList() {
  const main = $("#main");
  main.innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between"><h2 style="margin:0">รายการของที่รับบริจาค</h2>
      <button class="btn btn-outline btn-sm" id="export-list">ส่งออก Excel</button></div>
    ${filterBar("list")}
    <div class="table-wrap" id="list-table"></div>
  </div></div>`;
  const bar = $("[data-filter=list]");
  wireFilter(bar, load);
  $("#export-list").onclick = () => {
    location.href = `/api/export/donations.xlsx?${filterQuery(bar)}`;
  };
  async function load(q) {
    const data = await api(`/api/donations?${q}`);
    const rows = data.donations || [];
    if (!rows.length) {
      $("#list-table").innerHTML = `<p class="empty">ไม่มีรายการ</p>`;
      return;
    }
    $("#list-table").innerHTML = `<table>
      <thead><tr><th>วันที่</th><th>รหัสสาขา</th><th>ชื่อร้าน</th><th class="num">จำนวนชิ้น</th><th class="num">น้ำหนัก (กก.)</th><th>แหล่ง</th><th></th></tr></thead>
      <tbody>
        ${rows
          .map(
            (r) => `<tr>
          <td>${fmtDate(r.pickupDate || r.date)}</td>
          <td>${r.branchCode}</td>
          <td>${r.storeName}</td>
          <td class="num">${fmtNum(r.pieces)}</td>
          <td class="num">${fmtNum(r.weightKg, 2)}</td>
          <td><span class="badge">${r.source === "public-form" ? "ฟอร์มสาธารณะ" : "เว็บ"}</span></td>
          <td><button class="btn btn-ghost btn-sm" data-del="${r.id}">ลบ</button></td>
        </tr>`
          )
          .join("")}
        <tr><td colspan="3"><strong>รวม</strong> ${data.totals.totalRecords} รายการ</td>
          <td class="num"><strong>${fmtNum(data.totals.totalPieces)}</strong></td>
          <td class="num"><strong>${fmtNum(data.totals.totalWeight, 2)}</strong></td><td></td><td></td></tr>
      </tbody>
    </table>`;
    $("#list-table").querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("ลบรายการนี้?")) return;
        await api(`/api/donations/${btn.dataset.del}`, { method: "DELETE" });
        toast("ลบรายการแล้ว");
        load(filterQuery(bar));
      };
    });
  }
}

async function renderBranchReport() {
  const y = state.cursor.getFullYear();
  const m = state.cursor.getMonth() + 1;
  const data = await api(`/api/reports/by-branch?year=${y}&month=${m}`);
  $("#main").innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between"><h2 style="margin:0">สรุปตามสาขา — ${data.label}</h2>
      <a class="btn btn-outline btn-sm" href="/api/export/branches.xlsx?year=${y}&month=${m}">ส่งออก Excel</a></div>
    <div class="grid-3" style="margin:1rem 0">
      <div class="card stat"><div class="stat-icon">🏪</div><div><p class="muted">จำนวนสาขา</p><p class="stat-value">${fmtNum(data.totals.branchCount || 0)}</p></div></div>
      <div class="card stat"><div class="stat-icon">📥</div><div><p class="muted">จำนวนครั้งรวม</p><p class="stat-value">${fmtNum(data.totals.totalRecords)}</p></div></div>
      <div class="card stat"><div class="stat-icon">📦</div><div><p class="muted">จำนวนชิ้นรวม</p><p class="stat-value">${fmtNum(data.totals.totalPieces)}</p></div></div>
    </div>
    ${
      data.rows.length
        ? `<div class="table-wrap"><table>
      <thead><tr><th>รหัสสาขา</th><th>ชื่อร้าน</th><th class="num">จำนวนครั้ง</th><th class="num">จำนวนชิ้น</th><th class="num">น้ำหนัก (กก.)</th></tr></thead>
      <tbody>${data.rows
        .map(
          (r) => `<tr><td>${r.branchCode}</td><td>${r.storeName}</td><td class="num">${fmtNum(r.count)}</td><td class="num">${fmtNum(r.pieces)}</td><td class="num">${fmtNum(r.weight, 2)}</td></tr>`
        )
        .join("")}
        <tr><td colspan="2"><strong>รวมทั้งหมด</strong></td><td class="num"><strong>${fmtNum(data.totals.totalRecords)}</strong></td>
          <td class="num"><strong>${fmtNum(data.totals.totalPieces)}</strong></td>
          <td class="num"><strong>${fmtNum(data.totals.totalWeight, 2)}</strong></td></tr>
      </tbody></table></div>`
        : `<p class="empty">ไม่มีข้อมูล</p>`
    }
  </div></div>`;
}

async function renderGroups() {
  const data = await api("/api/groups");
  state.groups = data.groups;
  $("#main").innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between">
      <h2 style="margin:0">กลุ่มรับของ</h2>
      <button class="btn btn-sm" id="new-group">${icon("plus")} สร้างกลุ่มใหม่</button>
    </div>
    <div id="group-list" style="margin-top:1rem"></div>
  </div></div>`;
  const list = $("#group-list");
  if (!data.groups.length) {
    list.innerHTML = `<p class="empty">ยังไม่มีกลุ่มรับของ<br/>กดปุ่ม สร้างกลุ่มใหม่ เพื่อเริ่มต้น</p>`;
  } else {
    list.innerHTML = data.groups
      .map(
        (g) => `<div class="card group-card">
        <div class="flex-between">
          <div><strong>${g.name}</strong><p class="muted">${g.description || ""} — ${g.members.length} สาขา</p></div>
          <div class="row-actions">
            <button class="btn btn-outline btn-sm" data-edit="${g.id}">แก้ไข</button>
            <button class="btn btn-ghost btn-sm" data-del="${g.id}">ลบ</button>
          </div>
        </div>
      </div>`
      )
      .join("");
  }
  $("#new-group").onclick = () => openGroupDialog();
  list.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => openGroupDialog(data.groups.find((g) => g.id == b.dataset.edit))));
  list.querySelectorAll("[data-del]").forEach(
    (b) =>
      (b.onclick = async () => {
        if (!confirm("ลบกลุ่มนี้?")) return;
        try {
          await api(`/api/groups/${b.dataset.del}`, { method: "DELETE" });
          toast("ลบกลุ่มแล้ว");
          renderGroups();
        } catch (e) {
          toast("ลบกลุ่มไม่สำเร็จ", true);
        }
      })
  );
}

function openGroupDialog(group) {
  const selected = new Set(group ? group.members : []);
  const overlay = document.createElement("div");
  overlay.className = "dialog-bg";
  overlay.innerHTML = `<div class="card dialog"><div class="card-body">
    <h2 style="margin-top:0">${group ? "แก้ไขกลุ่ม" : "สร้างกลุ่มใหม่"}</h2>
    <div class="field"><label>ชื่อกลุ่ม *</label><input class="input" id="g-name" value="${group ? group.name : ""}" placeholder="เช่น สายเมืองเอก" /></div>
    <div class="field"><label>รายละเอียด</label><textarea class="textarea" id="g-desc" placeholder="เช่น รับของทุกวันจันทร์-ศุกร์">${group ? group.description || "" : ""}</textarea></div>
    <div class="field"><label>ค้นหารหัสหรือชื่อสาขา...</label><input class="input" id="g-search" /></div>
    <div class="muted" id="g-count">เลือกสาขา (${selected.size} สาขา)</div>
    <div class="checks" id="g-checks"></div>
    <div class="flex-between" style="margin-top:1rem">
      <button class="btn btn-outline" id="g-cancel">ยกเลิก</button>
      <button class="btn" id="g-save">บันทึก</button>
    </div>
  </div></div>`;
  document.body.append(overlay);
  const paint = () => {
    const q = ($("#g-search").value || "").toLowerCase();
    const used = new Set();
    state.groups.forEach((g) => {
      if (group && g.id === group.id) return;
      g.members.forEach((c) => used.add(c));
    });
    $("#g-checks").innerHTML = state.branches
      .filter((b) => (!q || b.code.includes(q) || b.name.toLowerCase().includes(q)) && (!used.has(b.code) || selected.has(b.code)))
      .map(
        (b) => `<label class="check"><input type="checkbox" value="${b.code}" ${selected.has(b.code) ? "checked" : ""} /> ${b.code} ${b.name}</label>`
      )
      .join("");
    $("#g-checks").querySelectorAll("input").forEach((inp) => {
      inp.onchange = () => {
        if (inp.checked) selected.add(inp.value);
        else selected.delete(inp.value);
        $("#g-count").textContent = `เลือกสาขา (${selected.size} สาขา)`;
      };
    });
    $("#g-count").textContent = `เลือกสาขา (${selected.size} สาขา)`;
  };
  $("#g-search").oninput = paint;
  paint();
  $("#g-cancel").onclick = () => overlay.remove();
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  $("#g-save").onclick = async () => {
    const name = $("#g-name").value.trim();
    if (!name) {
      toast("กรุณาใส่ชื่อกลุ่ม", true);
      return;
    }
    const body = JSON.stringify({ name, description: $("#g-desc").value, members: [...selected] });
    try {
      if (group) {
        await api(`/api/groups/${group.id}`, { method: "PUT", body });
        toast("แก้ไขกลุ่มสำเร็จ");
      } else {
        await api("/api/groups", { method: "POST", body });
        toast("สร้างกลุ่มสำเร็จ");
      }
      overlay.remove();
      renderGroups();
    } catch (e) {
      toast(group ? "แก้ไขกลุ่มไม่สำเร็จ" : "สร้างกลุ่มไม่สำเร็จ", true);
    }
  };
}

async function renderGroupReport() {
  $("#main").innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between"><h2 style="margin:0">รายงานตามกลุ่ม</h2>
      <div style="display:flex;gap:.5rem">
        <button class="btn btn-outline btn-sm" id="copy-all">คัดลอกรายงานทุกกลุ่ม</button>
        <button class="btn btn-outline btn-sm" id="export-g">ส่งออก Excel</button>
      </div>
    </div>
    ${filterBar("greport")}
    <div id="greport"></div>
  </div></div>`;
  const bar = $("[data-filter=greport]");
  wireFilter(bar, load);
  $("#export-g").onclick = () => (location.href = `/api/export/groups.xlsx?${filterQuery(bar)}`);
  $("#copy-all").onclick = async () => {
    const text = $("#greport").dataset.copy || "";
    if (!text) {
      toast("ไม่มีข้อมูลกลุ่มให้คัดลอก", true);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast("คัดลอกรายงานสำเร็จ");
    } catch {
      toast("คัดลอกไม่สำเร็จ", true);
    }
  };
  async function load(q) {
    const data = await api(`/api/reports/by-group?${q}`);
    const groups = data.groups || [];
    let copy = `📋 สรุปรายงานตามกลุ่มรับของ\n📅 ${todayISO()}\n${"─".repeat(20)}\n`;
    let allPieces = 0;
    $("#greport").innerHTML = groups
      .map((g) => {
        allPieces += g.totalPieces;
        const lines = g.records.map((r, i) => `  ${i + 1}. ${r.branchCode} ${r.storeName} - ${r.pieces} ชิ้น`).join("\n");
        copy += `\n🏷️ ${g.groupName}\n${lines}\n  รวม: ${g.totalPieces.toLocaleString()} ชิ้น\n`;
        return `<div class="card group-card">
          <div class="flex-between"><strong>${g.groupName}</strong>
            <span class="muted">${g.totalRecords} รายการ · ${fmtNum(g.totalPieces)} ชิ้น · ${fmtNum(g.totalWeight, 2)} กก.</span></div>
          <div class="table-wrap">${
            g.records.length
              ? `<table><thead><tr><th>ลำดับ</th><th>วันที่</th><th>รหัสสาขา</th><th>ชื่อร้าน</th><th class="num">จำนวนชิ้น</th><th class="num">น้ำหนัก (กก.)</th></tr></thead>
            <tbody>${g.records
              .map(
                (r, i) =>
                  `<tr><td>${i + 1}</td><td>${fmtDate(r.pickupDate || r.date)}</td><td>${r.branchCode}</td><td>${r.storeName}</td><td class="num">${fmtNum(r.pieces)}</td><td class="num">${fmtNum(r.weightKg, 2)}</td></tr>`
              )
              .join("")}</tbody></table>`
              : `<p class="empty">ไม่มีรายการ</p>`
          }</div>
        </div>`;
      })
      .join("");
    copy += `\n🏷️ รวมทั้งหมด: ${allPieces.toLocaleString()} ชิ้น`;
    $("#greport").dataset.copy = copy;
    if (!groups.length) $("#greport").innerHTML = `<p class="empty">ไม่มีข้อมูล</p>`;
  }
}

async function renderMaster() {
  const data = await api("/api/branches");
  state.branches = data.branches;
  $("#main").innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between"><h2 style="margin:0">ข้อมูลหลักสาขา</h2>
      <button class="btn btn-sm" id="add-branch">${icon("plus")} เพิ่มสาขา</button></div>
    <div class="field" style="margin-top:1rem"><input class="input" id="b-search" placeholder="ค้นหารหัสหรือชื่อสาขา..." /></div>
    <div class="table-wrap" id="b-table"></div>
  </div></div>`;
  const paint = () => {
    const q = ($("#b-search").value || "").toLowerCase();
    const rows = data.branches.filter((b) => b.code.includes(q) || b.name.toLowerCase().includes(q));
    $("#b-table").innerHTML = `<table>
      <thead><tr><th>ลำดับ</th><th>รหัสร้าน</th><th>ชื่อสาขา</th><th>ผู้ติดต่อ</th><th>ตำแหน่ง</th><th>เบอร์โทร</th><th></th></tr></thead>
      <tbody>${rows
        .map(
          (b, i) => `<tr>
        <td>${i + 1}</td><td>${b.code}</td><td>${b.name}</td>
        <td><input class="input" data-c="${b.code}" value="${b.contactName || ""}" /></td>
        <td><input class="input" data-p="${b.code}" value="${b.position || ""}" /></td>
        <td><input class="input" data-ph="${b.code}" value="${b.phone || ""}" /></td>
        <td><button class="btn btn-outline btn-sm" data-save="${b.code}">บันทึก</button></td>
      </tr>`
        )
        .join("")}</tbody></table>`;
    $("#b-table").querySelectorAll("[data-save]").forEach((btn) => {
      btn.onclick = async () => {
        const code = btn.dataset.save;
        try {
          await api(`/api/branch-contacts/${code}`, {
            method: "PUT",
            body: JSON.stringify({
              contactName: $(`[data-c="${code}"]`).value,
              position: $(`[data-p="${code}"]`).value,
              phone: $(`[data-ph="${code}"]`).value,
            }),
          });
          toast("บันทึกสำเร็จ");
        } catch {
          toast("บันทึกไม่สำเร็จ", true);
        }
      };
    });
  };
  $("#b-search").oninput = paint;
  paint();
  $("#add-branch").onclick = () => {
    const overlay = document.createElement("div");
    overlay.className = "dialog-bg";
    overlay.innerHTML = `<div class="card dialog"><div class="card-body">
      <h2 style="margin-top:0">เพิ่มสาขาใหม่</h2>
      <div class="field"><label>รหัสร้าน *</label><input class="input" id="nb-code" placeholder="เช่น 12345" /></div>
      <div class="field"><label>ชื่อสาขา *</label><input class="input" id="nb-name" /></div>
      <div class="field"><label>ผู้ติดต่อ</label><input class="input" id="nb-c" /></div>
      <div class="field"><label>ตำแหน่ง</label><input class="input" id="nb-p" /></div>
      <div class="field"><label>เบอร์โทร</label><input class="input" id="nb-ph" /></div>
      <div class="flex-between"><button class="btn btn-outline" id="nb-cancel">ยกเลิก</button><button class="btn" id="nb-save">บันทึก</button></div>
    </div></div>`;
    document.body.append(overlay);
    $("#nb-cancel").onclick = () => overlay.remove();
    $("#nb-save").onclick = async () => {
      try {
        await api("/api/branches", {
          method: "POST",
          body: JSON.stringify({
            code: $("#nb-code").value,
            name: $("#nb-name").value,
            contactName: $("#nb-c").value,
            position: $("#nb-p").value,
            phone: $("#nb-ph").value,
          }),
        });
        toast("เพิ่มสาขาสำเร็จ");
        overlay.remove();
        renderMaster();
      } catch (e) {
        toast(e.message, true);
      }
    };
  };
}

async function renderLine() {
  const data = await api("/api/line-groups");
  $("#main").innerHTML = `<div class="card"><div class="card-body">
    <div class="flex-between"><h2 style="margin:0">กลุ่ม LINE แจ้งเตือน</h2>
      <button class="btn btn-sm" id="add-line">${icon("plus")} เพิ่มกลุ่ม LINE</button></div>
    <p class="muted">ดู Group ID ได้จาก Webhook event เมื่อเพิ่ม Bot เข้ากลุ่ม LINE (หรือระบบจะบันทึกให้อัตโนมัติ)</p>
    <p class="muted">Webhook: <code>${location.origin}/api/line/webhook</code></p>
    <div id="line-list" style="margin-top:1rem"></div>
  </div></div>`;
  const list = $("#line-list");
  if (!data.groups.length) list.innerHTML = `<p class="empty">ยังไม่มีกลุ่ม LINE</p>`;
  else {
    list.innerHTML = data.groups
      .map(
        (g) => `<div class="card group-card flex-between">
        <div><strong>${g.name}</strong><p class="muted">${g.group_id} · ${g.message_type === "full" ? "ข้อความเต็ม + รูป" : "ข้อความย่อ (รับของ)"}</p></div>
        <button class="btn btn-ghost btn-sm" data-del="${g.id}">ลบ</button>
      </div>`
      )
      .join("");
    list.querySelectorAll("[data-del]").forEach(
      (b) =>
        (b.onclick = async () => {
          await api(`/api/line-groups/${b.dataset.del}`, { method: "DELETE" });
          toast("ลบกลุ่ม LINE แล้ว");
          renderLine();
        })
    );
  }
  $("#add-line").onclick = () => {
    const overlay = document.createElement("div");
    overlay.className = "dialog-bg";
    overlay.innerHTML = `<div class="card dialog"><div class="card-body">
      <h2 style="margin-top:0">เพิ่มกลุ่ม LINE ใหม่</h2>
      <div class="field"><label>ชื่อกลุ่ม</label><input class="input" id="ln-name" placeholder="เช่น กลุ่มรับของหลัก" /></div>
      <div class="field"><label>Group ID</label><input class="input" id="ln-id" placeholder="เช่น C1234567890abcdef..." /></div>
      <div class="field"><label>รูปแบบข้อความ *</label>
        <select class="select" id="ln-type">
          <option value="summary">ข้อความย่อ - รับของ (รหัสสาขา, ชื่อสาขา, จำนวนชิ้น)</option>
          <option value="full">ข้อความเต็ม + รูปภาพ (วันที่, รหัส, ชื่อ, จำนวน, ผู้ติดต่อ, เบอร์โทร)</option>
          <option value="short">ข้อความย่อ - รับของ (รูปแบบ short)</option>
        </select>
      </div>
      <div class="flex-between"><button class="btn btn-outline" id="ln-cancel">ยกเลิก</button><button class="btn" id="ln-save">บันทึก</button></div>
    </div></div>`;
    document.body.append(overlay);
    $("#ln-cancel").onclick = () => overlay.remove();
    $("#ln-save").onclick = async () => {
      try {
        await api("/api/line-groups", {
          method: "POST",
          body: JSON.stringify({ name: $("#ln-name").value, group_id: $("#ln-id").value, message_type: $("#ln-type").value }),
        });
        toast("เพิ่มกลุ่ม LINE สำเร็จ");
        overlay.remove();
        renderLine();
      } catch (e) {
        toast(e.message, true);
      }
    };
  };
}

async function bootDashboard() {
  const branches = await api("/api/branches");
  state.branches = branches.branches;
  dashboardShell();
  switchTab("entry");
}

async function start() {
  if (PAGE === "donate") {
    renderDonate();
    return;
  }
  if (PAGE === "reset") {
    renderReset();
    return;
  }
  try {
    const me = await api("/api/me");
    if (me.user) {
      state.user = me.user;
      await bootDashboard();
    } else {
      renderLogin();
    }
  } catch {
    renderLogin();
  }
}

start();
