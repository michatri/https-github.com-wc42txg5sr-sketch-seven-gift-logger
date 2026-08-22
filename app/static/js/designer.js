(() => {
  const boot = JSON.parse(document.getElementById("boot").textContent);
  const page = document.getElementById("page");
  const palette = document.getElementById("field-palette");
  const status = document.getElementById("save-status");
  const listConfig = document.getElementById("list-config");
  const columnList = document.getElementById("column-list");
  const pageWrap = document.getElementById("page-wrap");
  const headerBand = document.getElementById("header-band");

  const state = {
    id: boot.id,
    name: boot.name || "",
    source: boot.source || "members",
    layout: boot.layout || { mode: "form", orientation: "P", header: true, elements: [], columns: [] },
    fields: boot.fields || [],
    sample: boot.sample || {},
    selected: null,
  };
  if (!state.layout.elements) state.layout.elements = [];
  if (!state.layout.columns) state.layout.columns = [];

  const $ = (id) => document.getElementById(id);
  $("report-name").value = state.name;
  $("report-source").value = state.source;
  $("report-mode").value = state.layout.mode || "form";
  $("report-orient").value = state.layout.orientation || "P";
  $("report-header").checked = state.layout.header !== false;

  function uid() {
    return "e" + Math.random().toString(36).slice(2, 9);
  }

  function mmToPx() {
    return page.clientWidth / ((state.layout.orientation === "L") ? 297 : 210);
  }

  function nextY() {
    const els = state.layout.elements;
    if (!els.length) return state.layout.header !== false ? 48 : 18;
    const last = els[els.length - 1];
    return Math.min(270, Number(last.y || 48) + Number(last.h || 8) + 3);
  }

  function fieldLabel(key) {
    const found = state.fields.find((f) => f.key === key);
    return found ? found.label : key;
  }

  function renderPalette() {
    palette.innerHTML = "";
    state.fields.forEach((f) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "palette-item";
      b.textContent = f.label;
      b.addEventListener("click", () => addField(f.key, f.label));
      palette.appendChild(b);
    });
  }

  function addField(key, label) {
    if ((state.layout.mode || "form") === "list") {
      if (!state.layout.columns.some((c) => c.field === key)) {
        state.layout.columns.push({ field: key, label, w: 28 });
      }
      renderColumns();
      return;
    }
    state.layout.elements.push({
      id: uid(),
      type: "field",
      field: key,
      label,
      show_label: true,
      x: 18,
      y: nextY(),
      w: 170,
      h: 8,
      size: 12,
      bold: false,
      align: "L",
    });
    renderPage();
  }

  function renderColumns() {
    columnList.innerHTML = "";
    state.layout.columns.forEach((col, idx) => {
      const row = document.createElement("div");
      row.className = "col-row";
      row.innerHTML = `<span>${col.label}</span>`;
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "btn small danger";
      rm.textContent = "ลบคอลัมน์";
      rm.addEventListener("click", () => {
        state.layout.columns.splice(idx, 1);
        renderColumns();
      });
      row.appendChild(rm);
      columnList.appendChild(row);
    });
  }

  function sampleValue(el) {
    if (el.type === "text") return el.text || "ข้อความ";
    if (el.type === "line") return "";
    const raw = state.sample[el.field];
    const val = raw == null || raw === "" ? "…" : raw;
    return el.show_label && el.label ? `${el.label}: ${val}` : val;
  }

  function renderPage() {
    const landscape = state.layout.orientation === "L";
    page.classList.toggle("landscape", landscape);
    headerBand.hidden = state.layout.header === false;
    const form = (state.layout.mode || "form") === "form";
    pageWrap.hidden = !form;
    listConfig.hidden = form;
    [...page.querySelectorAll(".el")].forEach((n) => n.remove());
    if (!form) {
      renderColumns();
      return;
    }
    state.layout.elements.forEach((el) => {
      const box = document.createElement("div");
      box.className = "el" + (state.selected === el.id ? " selected" : "");
      box.dataset.id = el.id;
      box.style.left = el.x + "mm";
      box.style.top = el.y + "mm";
      box.style.width = el.w + "mm";
      box.style.height = (el.h || 8) + "mm";
      box.style.fontSize = (el.size || 12) + "px";
      box.style.fontWeight = el.bold ? "700" : "400";
      box.style.textAlign = el.align === "C" ? "center" : el.align === "R" ? "right" : "left";
      box.textContent = el.type === "line" ? "" : sampleValue(el);
      if (el.type === "line") box.classList.add("el-line");
      box.addEventListener("mousedown", (ev) => startDrag(ev, el));
      box.addEventListener("click", (ev) => {
        ev.stopPropagation();
        select(el.id);
      });
      page.appendChild(box);
    });
  }

  function select(id) {
    state.selected = id;
    const el = state.layout.elements.find((e) => e.id === id);
    $("prop-empty").hidden = !!el;
    $("prop-box").hidden = !el;
    if (el) {
      $("prop-label").value = el.label || "";
      $("prop-text").value = el.text || "";
      $("prop-show-label").checked = !!el.show_label;
      $("prop-size").value = el.size || 12;
      $("prop-w").value = el.w || 80;
      $("prop-h").value = el.h || 8;
      $("prop-bold").checked = !!el.bold;
      $("prop-align").value = el.align || "L";
    }
    renderPage();
  }

  function currentEl() {
    return state.layout.elements.find((e) => e.id === state.selected);
  }

  function startDrag(ev, el) {
    if (ev.button !== 0) return;
    ev.preventDefault();
    select(el.id);
    const scale = mmToPx();
    const startX = ev.clientX;
    const startY = ev.clientY;
    const ox = Number(el.x);
    const oy = Number(el.y);
    const move = (e) => {
      el.x = Math.max(8, Math.min(190, ox + (e.clientX - startX) / scale));
      el.y = Math.max(8, Math.min(280, oy + (e.clientY - startY) / scale));
      renderPage();
    };
    const up = () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  ["prop-label", "prop-text", "prop-size", "prop-w", "prop-h", "prop-align"].forEach((id) => {
    $(id).addEventListener("input", () => {
      const el = currentEl();
      if (!el) return;
      if (id === "prop-label") el.label = $("prop-label").value;
      if (id === "prop-text") el.text = $("prop-text").value;
      if (id === "prop-size") el.size = Number($("prop-size").value) || 12;
      if (id === "prop-w") el.w = Number($("prop-w").value) || 80;
      if (id === "prop-h") el.h = Number($("prop-h").value) || 8;
      if (id === "prop-align") el.align = $("prop-align").value;
      renderPage();
    });
  });
  $("prop-show-label").addEventListener("change", () => {
    const el = currentEl();
    if (el) el.show_label = $("prop-show-label").checked;
    renderPage();
  });
  $("prop-bold").addEventListener("change", () => {
    const el = currentEl();
    if (el) el.bold = $("prop-bold").checked;
    renderPage();
  });
  $("btn-del").addEventListener("click", () => {
    state.layout.elements = state.layout.elements.filter((e) => e.id !== state.selected);
    state.selected = null;
    select(null);
    renderPage();
  });

  $("btn-text").addEventListener("click", () => {
    const text = prompt("ข้อความบนรายงาน", "หัวข้อรายงาน") || "หัวข้อรายงาน";
    state.layout.elements.push({
      id: uid(), type: "text", text, x: 18, y: nextY(), w: 170, h: 10, size: 16, bold: true, align: "C",
    });
    renderPage();
  });
  $("btn-line").addEventListener("click", () => {
    state.layout.elements.push({ id: uid(), type: "line", x: 18, y: nextY(), w: 174, h: 0.5 });
    renderPage();
  });

  $("report-mode").addEventListener("change", () => {
    state.layout.mode = $("report-mode").value;
    renderPage();
  });
  $("report-orient").addEventListener("change", () => {
    state.layout.orientation = $("report-orient").value;
    renderPage();
  });
  $("report-header").addEventListener("change", () => {
    state.layout.header = $("report-header").checked;
    renderPage();
  });
  $("report-source").addEventListener("change", async () => {
    const source = $("report-source").value;
    const res = await fetch(`/api/designer/sample?source=${encodeURIComponent(source)}`);
    const data = await res.json();
    state.source = source;
    state.fields = (data.fields || []).map(([key, label]) => ({ key, label }));
    state.sample = data.record || {};
    state.layout.elements = [];
    state.layout.columns = [];
    renderPalette();
    renderPage();
  });

  async function save() {
    const name = $("report-name").value.trim();
    if (!name) {
      status.textContent = "กรุณาตั้งชื่อรายงาน";
      $("report-name").focus();
      return null;
    }
    status.textContent = "กำลังบันทึก...";
    const res = await fetch("/designer/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: state.id,
        name,
        source: $("report-source").value,
        layout: state.layout,
      }),
    });
    const data = await res.json();
    if (!data.ok) {
      status.textContent = data.error || "บันทึกไม่สำเร็จ";
      return null;
    }
    state.id = data.id;
    status.textContent = "บันทึกแล้ว";
    if (!boot.id) history.replaceState({}, "", `/designer/${data.id}`);
    return data.id;
  }

  $("btn-save").addEventListener("click", save);
  $("btn-pdf").addEventListener("click", async () => {
    const id = await save();
    if (!id) return;
    const q = encodeURIComponent($("pdf-q").value.trim());
    window.location.href = `/designer/${id}/pdf?q=${q}`;
  });

  page.addEventListener("click", () => select(null));
  renderPalette();
  renderPage();
})();
