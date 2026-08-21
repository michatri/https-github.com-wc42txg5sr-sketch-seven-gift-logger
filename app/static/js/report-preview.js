const bootEl = document.getElementById("pv-boot");
const boot = JSON.parse(bootEl.textContent);
const reportId = boot.id;
let page = 1;
const pageSize = 40;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function paramValues() {
  const out = {};
  document.querySelectorAll("[data-param]").forEach((inp) => {
    out[inp.dataset.param] = inp.value;
  });
  return out;
}

function renderParams() {
  const box = document.getElementById("pv-params");
  if (!box) return;
  const params = boot.parameters || [];
  if (!params.length) {
    box.innerHTML = '<p class="muted">รายงานนี้ไม่มีพารามิเตอร์ — กดดูรายงานได้เลย</p><button type="button" class="btn gold" id="pv-run">ดูรายงาน</button>';
    document.getElementById("pv-run").onclick = () => run();
    return;
  }
  box.innerHTML =
    "<h3>เงื่อนไขรายงาน</h3>" +
    params
      .map((p) => {
        const type = p.data_type === "date" ? "date" : "text";
        const opts = p.options || [];
        if (opts.length) {
          return `<div class="field"><label>${esc(p.label || p.name)}</label>
            <select data-param="${esc(p.name)}"><option value="">ทุกค่า</option>
            ${opts.map((o) => `<option value="${esc(o.value ?? o)}">${esc(o.label ?? o)}</option>`).join("")}
            </select></div>`;
        }
        return `<div class="field"><label>${esc(p.label || p.name)}</label>
          <input data-param="${esc(p.name)}" type="${type}" value="${esc(p.default_value || "")}"></div>`;
      })
      .join("") +
    '<button type="button" class="btn gold" id="pv-run">ดูรายงาน</button>';
  document.getElementById("pv-run").onclick = () => {
    page = 1;
    run();
  };
}

async function run() {
  const state = document.getElementById("pv-state");
  const paper = document.getElementById("pv-paper");
  state.innerHTML = '<div class="rp-state">กำลังโหลด…</div>';
  paper.innerHTML = "";
  try {
    const res = await fetch("/api/reports/" + reportId + "/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: paramValues(), page, pageSize }),
    });
    const data = await res.json();
    if (!data.ok) {
      state.innerHTML = `<div class="rp-state error">${esc(data.error || "ไม่สามารถสร้างรายงานได้")}</div>`;
      return;
    }
    if (data.status === "empty" || !data.rows || !data.rows.length) {
      state.innerHTML = '<div class="rp-state">ไม่มีข้อมูลตามเงื่อนไขที่เลือก</div>';
    } else {
      state.innerHTML = `<div class="muted">พบ ${data.total} แถว · หน้า ${data.page}</div>`;
    }
    paper.innerHTML = data.html || "";
    const pager = document.getElementById("pv-pager");
    if (pager) {
      const pages = Math.max(1, Math.ceil((data.total || 0) / pageSize));
      pager.innerHTML = `<button class="btn ghost" id="pg-prev">ก่อนหน้า</button>
        <span>หน้า ${page} / ${pages}</span>
        <button class="btn ghost" id="pg-next">ถัดไป</button>`;
      document.getElementById("pg-prev").onclick = () => {
        page = Math.max(1, page - 1);
        run();
      };
      document.getElementById("pg-next").onclick = () => {
        page = Math.min(pages, page + 1);
        run();
      };
    }
    if (window.AUTO_PRINT && data.ok) {
      setTimeout(() => window.print(), 400);
    }
  } catch (err) {
    state.innerHTML = `<div class="rp-state error">${esc(err.message)}</div>`;
  }
}

if (document.getElementById("pv-title")) document.getElementById("pv-title").textContent = boot.name || "ดูตัวอย่าง";
const edit = document.getElementById("pv-edit");
if (edit) edit.href = "/reports/" + reportId + "/edit";
const printBtn = document.getElementById("pv-print");
if (printBtn) printBtn.onclick = () => (location.href = "/reports/" + reportId + "/print");
const pdfBtn = document.getElementById("pv-pdf");
if (pdfBtn)
  pdfBtn.onclick = async () => {
    const res = await fetch("/api/reports/" + reportId + "/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: paramValues() }),
    });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      return alert(j.error || "ส่งออก PDF ไม่ได้");
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (boot.name || "report") + ".pdf";
    a.click();
  };

renderParams();
run();
