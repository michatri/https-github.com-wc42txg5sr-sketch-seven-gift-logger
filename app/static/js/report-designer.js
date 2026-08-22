const boot = JSON.parse(document.getElementById("rd-boot").textContent);
const reportId = boot.id;
let layout = boot.layout || {};
let dataset = boot.dataset || {};
let selected = null;
let dirty = false;
let saveTimer = null;

const TOOLS = [
  ["text", "ข้อความ"],
  ["label", "ป้าย"],
  ["field", "ฟิลด์"],
  ["image", "รูป"],
  ["line", "เส้น"],
  ["rectangle", "กรอบ"],
  ["table", "ตาราง"],
  ["barcode", "บาร์โค้ด"],
  ["qrcode", "QR Code"],
  ["pageNumber", "เลขหน้า"],
  ["date", "วันที่"],
  ["pageBreak", "ขึ้นหน้าใหม่"],
  ["chart", "แผนภูมิ"],
  ["subreport", "รายงานย่อย"],
];

const SECTIONS = [
  ["reportHeader", "หัวรายงาน"],
  ["pageHeader", "หัวหน้า"],
  ["groupHeader", "หัวกลุ่ม"],
  ["detail", "รายละเอียด"],
  ["groupFooter", "ท้ายกลุ่ม"],
  ["pageFooter", "ท้ายหน้า"],
  ["reportFooter", "ท้ายรายงาน"],
];

function uid(prefix) {
  return prefix + Math.random().toString(36).slice(2, 8);
}

function ensureLayout() {
  if (!layout.page) layout.page = { size: "A4", orientation: "portrait", margin: { top: 15, right: 15, bottom: 15, left: 15 } };
  if (!layout.page.margin) layout.page.margin = { top: 15, right: 15, bottom: 15, left: 15 };
  if (!layout.sections) layout.sections = SECTIONS.map(([t]) => ({ id: t, type: t, height: t === "detail" ? 16 : 12, components: [] }));
  layout.sections.forEach((s) => {
    if (!s.components) s.components = [];
  });
}

function markDirty() {
  dirty = true;
  const el = document.getElementById("rd-status");
  el.textContent = "มีการแก้ไขที่ยังไม่บันทึก";
  el.className = "save-status dirty";
}

function fields() {
  const cfg = (dataset && dataset.query_config) || {};
  return cfg.fields || [];
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function pageSize() {
  const size = layout.page.size || "A4";
  const map = { A4: [210, 297], A5: [148, 210], Letter: [215.9, 279.4] };
  let [w, h] = map[size] || [Number(layout.page.customWidth) || 210, Number(layout.page.customHeight) || 297];
  if ((layout.page.orientation || "portrait") === "landscape") [w, h] = [h, w];
  return [w, h];
}

function renderLeft() {
  const cfg = dataset.query_config || {};
  const tables = {};
  (cfg.fields || []).forEach((f) => {
    tables[f.table || cfg.mainTable] = tables[f.table || cfg.mainTable] || [];
    tables[f.table || cfg.mainTable].push(f);
  });
  const params = boot.parameters || [];
  document.getElementById("rd-data").innerHTML =
    Object.entries(tables)
      .map(
        ([t, cols]) =>
          `<div class="tree-table">${esc(t)}</div>` +
          cols
            .map(
              (c) =>
                `<button type="button" class="tree-field" draggable="true" data-field="${esc(c.alias || c.column)}" data-label="${esc(c.label || c.column)}">${esc(c.label || c.column)}</button>`
            )
            .join("")
      )
      .join("") +
    `<div class="tree-table">พารามิเตอร์</div>` +
    (params.map((p) => `<div class="muted">:${esc(p.name)} — ${esc(p.label || "")}</div>`).join("") || '<div class="muted">ไม่มี</div>');
  document.getElementById("rd-tools").innerHTML = TOOLS.map(
    ([k, lab]) => `<button type="button" class="palette-item" draggable="true" data-tool="${k}">${lab}</button>`
  ).join("");
}

function bandOf(compId) {
  for (const sec of layout.sections) {
    if ((sec.components || []).some((c) => c.id === compId)) return sec;
  }
  return null;
}

function findComp(id) {
  for (const sec of layout.sections) {
    const c = (sec.components || []).find((x) => x.id === id);
    if (c) return c;
  }
  return null;
}

function renderCanvas() {
  ensureLayout();
  const [w, h] = pageSize();
  const wrap = document.getElementById("rd-canvas-wrap");
  wrap.innerHTML = `<div class="rp-paper" id="rd-paper" style="width:${w}mm;min-height:${h}mm"></div>`;
  const paper = document.getElementById("rd-paper");
  layout.sections.forEach((sec) => {
    const band = document.createElement("div");
    band.className = "rp-band";
    band.dataset.section = sec.type;
    band.style.minHeight = (sec.height || 12) + "mm";
    band.innerHTML = `<span class="rd-band-label">${SECTIONS.find((s) => s[0] === sec.type)?.[1] || sec.type}</span>`;
    band.addEventListener("dragover", (e) => e.preventDefault());
    band.addEventListener("drop", (e) => onDrop(e, sec));
    (sec.components || []).forEach((comp) => band.appendChild(compEl(comp)));
    paper.appendChild(band);
  });
}

function compEl(comp) {
  const d = document.createElement("div");
  d.className = "rp-comp" + (selected === comp.id ? " selected" : "");
  d.dataset.id = comp.id;
  d.style.left = (comp.x || 0) + "mm";
  d.style.top = (comp.y || 0) + "mm";
  d.style.width = (comp.w || 40) + "mm";
  d.style.height = (comp.h || 8) + "mm";
  d.style.fontSize = (comp.fontSize || 11) + "pt";
  d.style.fontWeight = comp.bold ? "700" : "400";
  d.style.fontStyle = comp.italic ? "italic" : "normal";
  d.style.textDecoration = comp.underline ? "underline" : "none";
  d.style.textAlign = comp.align || "left";
  d.style.color = comp.color || "#2b2118";
  d.style.background = comp.background || "transparent";
  if (comp.type === "line") d.style.borderTop = "1.5px solid #c9a227";
  if (comp.type === "table") d.textContent = "ตาราง · " + ((comp.columns || []).map((c) => c.label || c.field).join(" | ") || "ยังไม่มีคอลัมน์");
  else if (comp.type === "field") d.textContent = "[" + (comp.field || "ฟิลด์") + "]";
  else if (comp.type === "pageNumber") d.textContent = "หน้า #";
  else if (comp.type === "date") d.textContent = "วันที่";
  else d.textContent = comp.text || comp.type;
  d.addEventListener("mousedown", (e) => startDrag(e, comp, d));
  d.addEventListener("click", (e) => {
    e.stopPropagation();
    selected = comp.id;
    renderCanvas();
    renderProps();
  });
  return d;
}

function startDrag(e, comp, el) {
  if (e.button !== 0) return;
  selected = comp.id;
  const startX = e.clientX;
  const startY = e.clientY;
  const origX = comp.x || 0;
  const origY = comp.y || 0;
  function move(ev) {
    comp.x = Math.max(0, origX + (ev.clientX - startX) / 3.78);
    comp.y = Math.max(0, origY + (ev.clientY - startY) / 3.78);
    el.style.left = comp.x + "mm";
    el.style.top = comp.y + "mm";
    markDirty();
  }
  function up() {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    renderProps();
  }
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
}

function onDrop(e, sec) {
  e.preventDefault();
  const field = e.dataTransfer.getData("field");
  const tool = e.dataTransfer.getData("tool");
  const rect = e.currentTarget.getBoundingClientRect();
  const x = Math.max(0, (e.clientX - rect.left) / 3.78);
  const y = Math.max(0, (e.clientY - rect.top) / 3.78);
  if (field) {
    sec.components.push({
      id: uid("f"),
      type: "field",
      field,
      x,
      y,
      w: 50,
      h: 8,
      fontSize: 11,
    });
    markDirty();
    renderCanvas();
    return;
  }
  if (tool) addTool(tool, sec, x, y);
}

function addTool(kind, sec, x, y) {
  const base = { id: uid("c"), type: kind, x: x || 4, y: y || 4, w: 50, h: kind === "table" ? 16 : 8, fontSize: 11, text: "" };
  if (kind === "text" || kind === "label") base.text = "ข้อความ";
  if (kind === "table") {
    base.columns = fields().map((f) => ({ field: f.alias || f.column, label: f.label || f.column, width: 28 }));
    base.header = true;
    base.footer = true;
    base.footerAgg = "COUNT";
    base.w = 180;
  }
  if (kind === "field") base.field = (fields()[0] || {}).alias || "";
  sec.components.push(base);
  selected = base.id;
  markDirty();
  renderCanvas();
  renderProps();
}

function renderProps() {
  const box = document.getElementById("rd-props");
  const comp = selected && findComp(selected);
  if (!comp) {
    box.innerHTML = '<p class="muted">เลือกองค์ประกอบบนกระดาษ</p>';
    const sec = layout.sections.find((s) => s.type === "groupHeader");
    box.innerHTML += `<div class="field"><label>จัดกลุ่ม</label><input id="p-group" value="${esc(layout.groupBy || (sec && sec.groupField) || "")}"></div>`;
    document.getElementById("p-group").addEventListener("change", (e) => {
      layout.groupBy = e.target.value;
      if (sec) sec.groupField = e.target.value;
      markDirty();
    });
    return;
  }
  const fieldOpts = fields()
    .map((f) => `<option value="${esc(f.alias || f.column)}">${esc(f.label || f.column)}</option>`)
    .join("");
  box.innerHTML = `
    <div class="field"><label>ชนิด</label><input value="${esc(comp.type)}" disabled></div>
    <div class="field"><label>ข้อความ</label><input id="p-text" value="${esc(comp.text || "")}"></div>
    <div class="field"><label>ฟิลด์</label><select id="p-field"><option value=""></option>${fieldOpts}</select></div>
    <div class="field"><label>รูปแบบข้อมูล</label>
      <select id="p-fmt">
        <option value="">ข้อความ</option>
        <option value="thaiDate">วันที่ไทย</option>
        <option value="date">วันที่</option>
        <option value="number">ตัวเลข</option>
        <option value="currency">เงิน</option>
        <option value="percentage">ร้อยละ</option>
      </select>
    </div>
    <div class="form-grid" style="grid-template-columns:1fr 1fr">
      <div class="field"><label>X</label><input id="p-x" type="number" value="${comp.x || 0}"></div>
      <div class="field"><label>Y</label><input id="p-y" type="number" value="${comp.y || 0}"></div>
      <div class="field"><label>กว้าง</label><input id="p-w" type="number" value="${comp.w || 40}"></div>
      <div class="field"><label>สูง</label><input id="p-h" type="number" value="${comp.h || 8}"></div>
    </div>
    <div class="field"><label>ฟอนต์ ขนาด</label><input id="p-size" type="number" value="${comp.fontSize || 11}"></div>
    <label><input type="checkbox" id="p-bold" ${comp.bold ? "checked" : ""}> ตัวหนา</label>
    <label><input type="checkbox" id="p-italic" ${comp.italic ? "checked" : ""}> ตัวเอียง</label>
    <label><input type="checkbox" id="p-under" ${comp.underline ? "checked" : ""}> ขีดเส้นใต้</label>
    <label><input type="checkbox" id="p-border" ${comp.border ? "checked" : ""}> เส้นขอบ</label>
    <div class="field"><label>จัดตำแหน่ง</label>
      <select id="p-align"><option value="left">ซ้าย</option><option value="center">กลาง</option><option value="right">ขวา</option></select>
    </div>
    <div class="field"><label>สี</label><input id="p-color" type="color" value="${comp.color || "#2b2118"}"></div>
    <div class="field"><label>พื้นหลัง</label><input id="p-bg" value="${esc(comp.background || "")}" placeholder="#ffffff"></div>
    <div class="field"><label>ระยะภายใน</label><input id="p-pad" type="number" value="${comp.padding || 0}"></div>
    ${comp.type === "table" ? tableProps(comp) : ""}
    <button type="button" class="btn danger small" id="p-del">ลบองค์ประกอบ</button>
  `;
  if (box.querySelector("#p-field")) box.querySelector("#p-field").value = comp.field || "";
  if (box.querySelector("#p-fmt")) box.querySelector("#p-fmt").value = comp.format || "";
  if (box.querySelector("#p-align")) box.querySelector("#p-align").value = comp.align || "left";
  const bind = (id, key, cast) => {
    const n = document.getElementById(id);
    if (!n) return;
    n.addEventListener("input", () => {
      let v = n.type === "checkbox" ? n.checked : n.value;
      if (cast === "num") v = Number(v);
      comp[key] = v;
      markDirty();
      renderCanvas();
    });
  };
  bind("p-text", "text");
  bind("p-field", "field");
  bind("p-fmt", "format");
  bind("p-x", "x", "num");
  bind("p-y", "y", "num");
  bind("p-w", "w", "num");
  bind("p-h", "h", "num");
  bind("p-size", "fontSize", "num");
  bind("p-bold", "bold");
  bind("p-italic", "italic");
  bind("p-under", "underline");
  bind("p-border", "border");
  bind("p-align", "align");
  bind("p-color", "color");
  bind("p-bg", "background");
  bind("p-pad", "padding", "num");
  document.getElementById("p-del").onclick = () => {
    const sec = bandOf(comp.id);
    if (sec) sec.components = sec.components.filter((c) => c.id !== comp.id);
    selected = null;
    markDirty();
    renderCanvas();
    renderProps();
  };
  if (comp.type === "table") wireTableProps(comp);
}

function tableProps(comp) {
  const cols = comp.columns || [];
  return `<h4>คอลัมน์ตาราง</h4>
    ${(cols || [])
      .map(
        (c, i) => `<div class="col-row">
      <input data-cl="${i}" value="${esc(c.label || "")}">
      <select data-cf="${i}">${fields()
          .map((f) => `<option value="${esc(f.alias || f.column)}" ${f.alias === c.field || f.column === c.field ? "selected" : ""}>${esc(f.label || f.column)}</option>`)
          .join("")}</select>
      <input data-cw="${i}" type="number" value="${c.width || 30}" style="width:64px">
      <select data-ca="${i}"><option value="">—</option><option value="SUM">SUM</option><option value="COUNT">COUNT</option><option value="AVG">AVG</option><option value="MIN">MIN</option><option value="MAX">MAX</option></select>
      <button type="button" class="btn small ghost" data-cup="${i}">↑</button>
      <button type="button" class="btn small ghost" data-cdn="${i}">↓</button>
      <button type="button" class="btn small danger" data-crm="${i}">ลบ</button>
    </div>`
      )
      .join("")}
    <button type="button" class="btn small ghost" id="col-add">+ คอลัมน์</button>
    <label><input type="checkbox" id="tbl-h" ${comp.header !== false ? "checked" : ""}> หัวตาราง</label>
    <label><input type="checkbox" id="tbl-f" ${comp.footer ? "checked" : ""}> ท้ายตาราง</label>`;
}

function wireTableProps(comp) {
  document.querySelectorAll("[data-cl]").forEach((n) =>
    n.addEventListener("input", () => {
      comp.columns[Number(n.dataset.cl)].label = n.value;
      markDirty();
      renderCanvas();
    })
  );
  document.querySelectorAll("[data-cf]").forEach((n) => {
    n.addEventListener("change", () => {
      comp.columns[Number(n.dataset.cf)].field = n.value;
      markDirty();
    });
  });
  document.querySelectorAll("[data-cw]").forEach((n) =>
    n.addEventListener("input", () => {
      comp.columns[Number(n.dataset.cw)].width = Number(n.value);
      markDirty();
    })
  );
  document.querySelectorAll("[data-ca]").forEach((n) => {
    n.value = comp.columns[Number(n.dataset.ca)].agg || "";
    n.addEventListener("change", () => {
      comp.columns[Number(n.dataset.ca)].agg = n.value;
      markDirty();
    });
  });
  document.querySelectorAll("[data-crm]").forEach((n) =>
    n.addEventListener("click", () => {
      comp.columns.splice(Number(n.dataset.crm), 1);
      markDirty();
      renderProps();
      renderCanvas();
    })
  );
  document.querySelectorAll("[data-cup]").forEach((n) =>
    n.addEventListener("click", () => {
      const i = Number(n.dataset.cup);
      if (i === 0) return;
      const c = comp.columns.splice(i, 1)[0];
      comp.columns.splice(i - 1, 0, c);
      markDirty();
      renderProps();
      renderCanvas();
    })
  );
  document.querySelectorAll("[data-cdn]").forEach((n) =>
    n.addEventListener("click", () => {
      const i = Number(n.dataset.cdn);
      if (i >= comp.columns.length - 1) return;
      const c = comp.columns.splice(i, 1)[0];
      comp.columns.splice(i + 1, 0, c);
      markDirty();
      renderProps();
      renderCanvas();
    })
  );
  document.getElementById("col-add").onclick = () => {
    const f = fields()[0] || { alias: "col", label: "คอลัมน์" };
    comp.columns = comp.columns || [];
    comp.columns.push({ field: f.alias || f.column, label: f.label || f.column, width: 30 });
    markDirty();
    renderProps();
    renderCanvas();
  };
  document.getElementById("tbl-h").onchange = (e) => {
    comp.header = e.target.checked;
    markDirty();
  };
  document.getElementById("tbl-f").onchange = (e) => {
    comp.footer = e.target.checked;
    markDirty();
  };
}

async function save(manual) {
  const el = document.getElementById("rd-status");
  el.textContent = "กำลังบันทึก…";
  el.className = "save-status saving";
  const name = boot.name || "รายงาน";
  const res = await fetch("/api/reports/" + reportId, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, layout, snapshot: !!manual }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    el.textContent = data.error || "บันทึกไม่สำเร็จ";
    el.className = "save-status dirty";
    return;
  }
  dirty = false;
  el.textContent = "บันทึกแล้ว";
  el.className = "save-status saved";
}

document.getElementById("rd-title").textContent = boot.name || "แก้ไขรายงาน";
document.getElementById("rd-preview").href = "/reports/" + reportId + "/preview";
document.getElementById("rd-print").href = "/reports/" + reportId + "/print";
document.getElementById("rd-save").onclick = () => save(true);
document.getElementById("rd-pdf").onclick = async () => {
  await save(false);
  const res = await fetch("/api/reports/" + reportId + "/pdf", { method: "POST", body: "{}" });
  if (!res.ok) return alert("ส่งออก PDF ไม่ได้");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (boot.name || "report") + ".pdf";
  a.click();
};
document.getElementById("rd-size").value = (layout.page && layout.page.size) || "A4";
document.getElementById("rd-orient").value = (layout.page && layout.page.orientation) || "portrait";
document.getElementById("rd-size").onchange = (e) => {
  layout.page.size = e.target.value;
  markDirty();
  renderCanvas();
};
document.getElementById("rd-orient").onchange = (e) => {
  layout.page.orientation = e.target.value;
  markDirty();
  renderCanvas();
};
document.querySelectorAll("[data-align]").forEach((b) =>
  b.addEventListener("click", () => {
    const c = selected && findComp(selected);
    if (!c) return;
    c.align = b.dataset.align;
    markDirty();
    renderCanvas();
    renderProps();
  })
);

document.getElementById("rd-data").addEventListener("dragstart", (e) => {
  if (e.target.dataset.field) e.dataTransfer.setData("field", e.target.dataset.field);
});
document.getElementById("rd-tools").addEventListener("click", (e) => {
  const kind = e.target.dataset.tool;
  if (!kind) return;
  const sec = layout.sections.find((s) => s.type === "detail") || layout.sections[0];
  addTool(kind, sec, 8, 4);
});
document.getElementById("rd-tools").addEventListener("dragstart", (e) => {
  if (e.target.dataset.tool) e.dataTransfer.setData("tool", e.target.dataset.tool);
});

window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    save(true);
  }
});

setInterval(() => {
  if (dirty) save(false);
}, 20000);

ensureLayout();
renderLeft();
renderCanvas();
renderProps();
