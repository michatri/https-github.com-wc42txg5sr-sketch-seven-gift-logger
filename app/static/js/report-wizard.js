const STEPS = [
  "เลือกแหล่งข้อมูล",
  "เลือกตารางหลัก",
  "เลือกฟิลด์",
  "ความสัมพันธ์",
  "ตัวกรอง",
  "ออกแบบรายงาน",
  "ดูตัวอย่าง",
  "บันทึก",
];

const OPS = [
  ["eq", "เท่ากับ"],
  ["ne", "ไม่เท่ากับ"],
  ["contains", "มีคำว่า"],
  ["gte", "มากกว่าหรือเท่ากับ"],
  ["lte", "น้อยกว่าหรือเท่ากับ"],
  ["is_null", "ว่าง"],
  ["is_not_null", "ไม่ว่าง"],
];

const state = {
  step: 1,
  data_source_id: null,
  catalog: { tables: [], relationships: [] },
  mainTable: "",
  fields: [],
  joins: [],
  filters: [],
  orderBy: [],
  groupBy: [],
  distinct: false,
  limit: 500,
  parameters: [],
  name: "",
  description: "",
  title: "",
  groupField: "",
};

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function api(url, opts) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || "ไม่สามารถสร้างรายงานได้");
  return data;
}

function tableByName(name) {
  return (state.catalog.tables || []).find((t) => t.name === name);
}

function queryConfig() {
  return {
    mainTable: state.mainTable,
    fields: state.fields.map((f) => ({
      table: f.table,
      column: f.column,
      alias: f.alias,
      label: f.label,
      agg: f.agg || null,
    })),
    joins: state.joins,
    filters: state.filters,
    orderBy: state.orderBy,
    groupBy: state.groupBy,
    distinct: state.distinct,
    limit: state.limit,
  };
}

function renderNav() {
  document.getElementById("wizard-nav").innerHTML = STEPS.map(
    (label, i) => `<li class="${state.step === i + 1 ? "on" : ""}" data-step="${i + 1}">${i + 1}. ${label}</li>`
  ).join("");
  document.getElementById("wizard-step-label").textContent = `ขั้นที่ ${state.step} จาก 8 — ${STEPS[state.step - 1]}`;
  document.getElementById("btn-prev").disabled = state.step === 1;
  document.getElementById("btn-next").textContent = state.step === 8 ? "บันทึกรายงาน" : "ถัดไป";
}

function fieldKey(f) {
  return f.table + "." + f.column;
}

async function render() {
  renderNav();
  const el = document.getElementById("wizard-body");
  if (state.step === 1) {
    const ds = await api("/api/data-sources");
    el.innerHTML = `<div class="pick-grid">${(ds.items || [])
      .map(
        (s) => `<div class="pick-card ${state.data_source_id === s.id ? "on" : ""}" data-src="${s.id}">
        <b>${esc(s.name)}</b><div class="muted">${esc(s.description || "")}</div></div>`
      )
      .join("")}</div>`;
    el.querySelectorAll("[data-src]").forEach((n) =>
      n.addEventListener("click", async () => {
        state.data_source_id = Number(n.dataset.src);
        state.catalog = await api("/api/data-sources/" + state.data_source_id + "/tables");
        render();
      })
    );
    return;
  }
  if (state.step === 2) {
    el.innerHTML = `<div class="pick-grid">${(state.catalog.tables || [])
      .map(
        (t) => `<div class="pick-card ${state.mainTable === t.name ? "on" : ""}" data-t="${esc(t.name)}">
        <b>${esc(t.label)}</b><div class="muted">${esc(t.name)} · ${t.columns.length} คอลัมน์</div></div>`
      )
      .join("")}</div>`;
    el.querySelectorAll("[data-t]").forEach((n) =>
      n.addEventListener("click", () => {
        state.mainTable = n.dataset.t;
        render();
      })
    );
    return;
  }
  if (state.step === 3) {
    const t = tableByName(state.mainTable) || { columns: [] };
    const selected = new Set(state.fields.map(fieldKey));
    el.innerHTML = `<div class="dual">
      <div><h3>ฟิลด์ในตาราง</h3><div class="chip-list" id="avail"></div></div>
      <div><h3>ฟิลด์ที่เลือก (ลากเรียงได้)</h3><div class="chip-list" id="sel"></div></div>
    </div>`;
    const avail = document.getElementById("avail");
    const sel = document.getElementById("sel");
    t.columns.forEach((c) => {
      const key = state.mainTable + "." + c.name;
      if (selected.has(key)) return;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "field-chip";
      b.textContent = c.label + " (" + c.name + ")";
      b.addEventListener("click", () => {
        state.fields.push({ table: state.mainTable, column: c.name, alias: c.name, label: c.label });
        render();
      });
      avail.appendChild(b);
    });
    state.fields.forEach((f, i) => {
      const b = document.createElement("div");
      b.className = "field-chip";
      b.draggable = true;
      b.textContent = (f.label || f.column) + "  ×";
      b.addEventListener("click", () => {
        state.fields.splice(i, 1);
        render();
      });
      b.addEventListener("dragstart", (ev) => ev.dataTransfer.setData("text/plain", String(i)));
      b.addEventListener("dragover", (ev) => ev.preventDefault());
      b.addEventListener("drop", (ev) => {
        ev.preventDefault();
        const from = Number(ev.dataTransfer.getData("text/plain"));
        const item = state.fields.splice(from, 1)[0];
        state.fields.splice(i, 0, item);
        render();
      });
      sel.appendChild(b);
    });
    return;
  }
  if (state.step === 4) {
    const rels = (state.catalog.relationships || []).filter(
      (r) => r.from_table === state.mainTable || r.to_table === state.mainTable
    );
    el.innerHTML = `<p class="muted">เลือกความสัมพันธ์ที่มีอยู่แล้วเท่านั้น ระบบจะไม่จอยให้อัตโนมัติ</p>
      <div id="rel-list"></div>
      <pre class="rel-box">${esc(state.mainTable)}\n${state.joins.map((j) => "  +---- " + j.table).join("\n")}</pre>`;
    const list = document.getElementById("rel-list");
    rels.forEach((r, idx) => {
      const other = r.from_table === state.mainTable ? r.to_table : r.from_table;
      const on = state.joins.some((j) => j.table === other);
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn ghost" + (on ? " gold" : "");
      b.textContent = (on ? "เอาออก · " : "เชื่อม · ") + r.label;
      b.addEventListener("click", () => {
        if (on) state.joins = state.joins.filter((j) => j.table !== other);
        else {
          const fromMain = r.from_table === state.mainTable;
          state.joins.push({
            table: other,
            type: "LEFT",
            left: fromMain ? r.from_table + "." + r.from_column : r.to_table + "." + r.to_column,
            right: fromMain ? r.to_table + "." + r.to_column : r.from_table + "." + r.from_column,
          });
        }
        render();
      });
      list.appendChild(b);
    });
    if (!rels.length) list.innerHTML = '<p class="muted">ไม่พบความสัมพันธ์ที่แนะนำสำหรับตารางนี้</p>';
    return;
  }
  if (state.step === 5) {
    const fieldOpts = state.fields.map((f) => `<option value="${esc(f.table + "." + f.column)}">${esc(f.label || f.column)}</option>`).join("");
    el.innerHTML = `
      <h3>ตัวกรอง</h3>
      <div id="filters"></div>
      <button type="button" class="btn ghost" id="add-filter">+ ตัวกรอง</button>
      <h3>เรียงลำดับ</h3>
      <select id="ord-field">${fieldOpts}</select>
      <select id="ord-dir"><option value="ASC">A→Z</option><option value="DESC">Z→A</option></select>
      <h3>จัดกลุ่ม</h3>
      <select id="grp-field"><option value="">— ไม่จัดกลุ่ม —</option>${fieldOpts}</select>
      <label class="muted"><input type="checkbox" id="distinct"> DISTINCT</label>
      <div class="field"><label>จำกัดจำนวนแถว (LIMIT / TOP)</label><input id="lim" type="number" min="1" max="2000" value="${state.limit}"></div>
      <p class="muted">พารามิเตอร์ใช้ชื่อ เช่น start_date, end_date, church, religion แล้วกรอกตอนดูรายงาน</p>
    `;
    const box = document.getElementById("filters");
    function drawFilters() {
      box.innerHTML = state.filters
        .map(
          (f, i) => `<div class="searchbar" data-i="${i}">
          <select data-k="field">${fieldOpts}</select>
          <select data-k="op">${OPS.map((o) => `<option value="${o[0]}">${o[1]}</option>`).join("")}</select>
          <input data-k="value" placeholder="ค่า หรือเว้นว่าง">
          <input data-k="param" placeholder="ชื่อพารามิเตอร์ เช่น start_date">
          <button type="button" class="btn small danger" data-rm="${i}">ลบ</button>
        </div>`
        )
        .join("");
      [...box.children].forEach((row, i) => {
        row.querySelector('[data-k="field"]').value = state.filters[i].field || "";
        row.querySelector('[data-k="op"]').value = state.filters[i].op || "eq";
        row.querySelector('[data-k="value"]').value = state.filters[i].value || "";
        row.querySelector('[data-k="param"]').value = state.filters[i].param || "";
        row.querySelectorAll("[data-k]").forEach((inp) =>
          inp.addEventListener("change", () => {
            state.filters[i][inp.dataset.k] = inp.value;
          })
        );
        row.querySelector("[data-rm]").addEventListener("click", () => {
          state.filters.splice(i, 1);
          drawFilters();
        });
      });
    }
    drawFilters();
    document.getElementById("add-filter").onclick = () => {
      const first = state.fields[0];
      state.filters.push({ field: first ? first.table + "." + first.column : "", op: "eq", value: "", param: "" });
      drawFilters();
    };
    document.getElementById("ord-field").value = (state.orderBy[0] && state.orderBy[0].field) || (state.fields[0] ? state.fields[0].table + "." + state.fields[0].column : "");
    document.getElementById("ord-dir").value = (state.orderBy[0] && state.orderBy[0].dir) || "ASC";
    document.getElementById("grp-field").value = state.groupBy[0] || "";
    document.getElementById("distinct").checked = state.distinct;
    document.getElementById("lim").value = state.limit;
    return;
  }
  if (state.step === 6) {
    el.innerHTML = `
      <div class="field"><label>หัวรายงาน</label><input id="title" value="${esc(state.title || state.name || "รายงาน")}"></div>
      <div class="field"><label>จัดกลุ่มบนกระดาษด้วยฟิลด์</label>
        <select id="gfield"><option value="">— ไม่จัดกลุ่ม —</option>
        ${state.fields.map((f) => `<option value="${esc(f.alias)}">${esc(f.label || f.alias)}</option>`).join("")}
        </select></div>
      <p class="muted">หลังบันทึก จะเปิดตัวออกแบบเต็มเพื่อลากข้อความ ตาราง บาร์โค้ด QR เส้น กรอบ ฯลฯ</p>
      <table>${state.fields.map((f, i) => `<tr><td>${i + 1}</td><td>${esc(f.column)}</td>
        <td><input data-lab="${i}" value="${esc(f.label || f.column)}"></td></tr>`).join("")}</table>
    `;
    document.getElementById("gfield").value = state.groupField;
    return;
  }
  if (state.step === 7) {
    el.innerHTML = '<div class="rp-state">กำลังโหลดตัวอย่าง…</div>';
    try {
      const r = await api("/api/query/preview", {
        method: "POST",
        body: JSON.stringify({ query_config: queryConfig(), page: 1, pageSize: 15 }),
      });
      el.innerHTML = `<p class="muted">พบ ${r.total} แถว (แสดงหน้าละ ${r.pageSize})</p>${r.html || ""}`;
    } catch (err) {
      el.innerHTML = `<div class="error">${esc(err.message)}</div>`;
    }
    return;
  }
  el.innerHTML = `
    <div class="field"><label>ชื่อรายงาน</label><input id="rname" value="${esc(state.name)}"></div>
    <div class="field"><label>คำอธิบาย</label><textarea id="rdesc">${esc(state.description)}</textarea></div>
    <div class="field"><label>สถานะ</label>
      <select id="rstatus"><option value="draft">ฉบับร่าง</option><option value="published">เผยแพร่</option></select>
    </div>
  `;
}

function collectStep() {
  if (state.step === 5) {
    const ord = document.getElementById("ord-field");
    if (ord) {
      state.orderBy = ord.value ? [{ field: ord.value, dir: document.getElementById("ord-dir").value }] : [];
      const g = document.getElementById("grp-field").value;
      state.groupBy = g ? [g] : [];
      state.distinct = document.getElementById("distinct").checked;
      state.limit = Number(document.getElementById("lim").value || 500);
    }
  }
  if (state.step === 6) {
    const title = document.getElementById("title");
    if (title) {
      state.title = title.value;
      state.groupField = document.getElementById("gfield").value;
      document.querySelectorAll("[data-lab]").forEach((inp) => {
        const i = Number(inp.dataset.lab);
        if (state.fields[i]) state.fields[i].label = inp.value;
      });
    }
  }
  if (state.step === 8) {
    const n = document.getElementById("rname");
    if (n) {
      state.name = n.value;
      state.description = document.getElementById("rdesc").value;
    }
  }
}

function parametersFromFilters() {
  const seen = new Set();
  const out = [];
  for (const f of state.filters) {
    const name = (f.param || "").replace(/^:/, "");
    if (!name || seen.has(name)) continue;
    seen.add(name);
    const labelMap = { start_date: "วันที่เริ่มต้น", end_date: "วันที่สิ้นสุด", church: "โบสถ์", religion: "ศาสนา" };
    out.push({
      name,
      label: labelMap[name] || name,
      data_type: name.includes("date") ? "date" : "text",
      default_value: f.value || "",
      required: false,
    });
  }
  return out;
}

async function save() {
  collectStep();
  if (!state.name.trim()) {
    state.name = state.title || "รายงานใหม่";
  }
  const fields = state.fields.map((f) => ({ ...f, alias: f.alias || f.column }));
  const statusEl = document.getElementById("save-status");
  statusEl.textContent = "กำลังบันทึก…";
  statusEl.className = "save-status saving";
  const r = await api("/api/reports", {
    method: "POST",
    body: JSON.stringify({
      name: state.name,
      description: state.description,
      data_source_id: state.data_source_id,
      query_config: { ...queryConfig(), fields },
      parameters: parametersFromFilters(),
      status: (document.getElementById("rstatus") || {}).value || "draft",
      layout: {
        version: 1,
        page: { size: "A4", orientation: "portrait", margin: { top: 15, right: 15, bottom: 15, left: 15 } },
        groupBy: state.groupField,
        sections: [
          {
            id: "reportHeader",
            type: "reportHeader",
            height: 18,
            components: [{ id: "t1", type: "text", text: state.title || state.name, x: 0, y: 2, w: 180, h: 10, fontSize: 16, bold: true, align: "center", color: "#6b1d2a" }],
          },
          { id: "pageHeader", type: "pageHeader", height: 8, components: [] },
          { id: "groupHeader", type: "groupHeader", height: 10, groupField: state.groupField, components: [] },
          {
            id: "detail",
            type: "detail",
            height: 14,
            components: [
              {
                id: "tbl1",
                type: "table",
                x: 0,
                y: 2,
                w: 180,
                h: 12,
                header: true,
                footer: true,
                footerAgg: "COUNT",
                columns: fields.map((f) => ({ field: f.alias, label: f.label || f.column, width: 30 })),
              },
            ],
          },
          { id: "groupFooter", type: "groupFooter", height: 8, components: [] },
          {
            id: "pageFooter",
            type: "pageFooter",
            height: 10,
            components: [
              { id: "pg", type: "pageNumber", x: 0, y: 1, w: 90, h: 6, fontSize: 8 },
              { id: "dt", type: "date", x: 90, y: 1, w: 90, h: 6, fontSize: 8, align: "right", format: "thaiDate" },
            ],
          },
          { id: "reportFooter", type: "reportFooter", height: 10, components: [] },
        ],
      },
    }),
  });
  statusEl.textContent = "บันทึกแล้ว";
  statusEl.className = "save-status saved";
  location.href = "/reports/" + r.id + "/edit";
}

document.getElementById("wizard-nav").addEventListener("click", (e) => {
  const li = e.target.closest("[data-step]");
  if (!li) return;
  collectStep();
  state.step = Number(li.dataset.step);
  render().catch((err) => alert(err.message));
});
document.getElementById("btn-prev").addEventListener("click", () => {
  collectStep();
  state.step = Math.max(1, state.step - 1);
  render().catch((err) => alert(err.message));
});
document.getElementById("btn-next").addEventListener("click", async () => {
  collectStep();
  if (state.step === 1 && !state.data_source_id) return alert("กรุณาเลือกแหล่งข้อมูล");
  if (state.step === 2 && !state.mainTable) return alert("กรุณาเลือกตาราง");
  if (state.step === 3 && !state.fields.length) return alert("กรุณาเลือกฟิลด์");
  if (state.step === 8) {
    try {
      await save();
    } catch (err) {
      alert(err.message);
    }
    return;
  }
  state.step += 1;
  render().catch((err) => alert(err.message));
});

api("/api/data-sources")
  .then((ds) => {
    if (ds.items && ds.items[0]) {
      state.data_source_id = ds.items[0].id;
      return api("/api/data-sources/" + state.data_source_id + "/tables");
    }
  })
  .then((cat) => {
    if (cat) state.catalog = cat;
    return render();
  })
  .catch((err) => {
    document.getElementById("wizard-body").innerHTML = `<div class="error">${esc(err.message)}</div>`;
  });
