async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || "ไม่สามารถสร้างรายงานได้");
  }
  return data;
}

const STATUS = { draft: "ฉบับร่าง", published: "เผยแพร่", archived: "เก็บถาวร" };
const scope = window.REPORT_SCOPE || "all";

function fmtDate(v) {
  if (!v) return "";
  return v.replace("T", " ").slice(0, 16);
}

async function load() {
  const q = document.getElementById("q").value;
  const status = document.getElementById("status").value;
  const sort = document.getElementById("sort").value;
  const dir = document.getElementById("dir").value;
  const params = new URLSearchParams({ q, status, sort, dir, scope });
  const data = await api("/api/reports?" + params.toString());
  const body = document.getElementById("report-rows");
  if (!data.items.length) {
    body.innerHTML = '<tr><td colspan="7" class="muted">ยังไม่มีรายงาน — กดสร้างรายงาน</td></tr>';
    return;
  }
  body.innerHTML = data.items.map((it) => `
    <tr>
      <td><a href="/reports/${it.id}/edit">${esc(it.name)}</a></td>
      <td>${esc(it.description || "")}</td>
      <td>${esc(it.created_by || "")}</td>
      <td>${esc(fmtDate(it.updated_at))}</td>
      <td><span class="badge">${STATUS[it.status] || it.status}</span></td>
      <td><button class="star" data-fav="${it.id}" data-on="${it.is_favorite ? 1 : 0}">${it.is_favorite ? "★" : "☆"}</button></td>
      <td class="actions">
        <a class="btn small ghost" href="/reports/${it.id}/preview">ดูตัวอย่าง</a>
        <a class="btn small ghost" href="/reports/${it.id}/print">พิมพ์</a>
        <button class="btn small gold" data-pdf="${it.id}">PDF</button>
        <a class="btn small ghost" href="/reports/${it.id}/edit">แก้ไข</a>
        <button class="btn small ghost" data-dup="${it.id}">สำเนา</button>
        <button class="btn small danger" data-del="${it.id}">ลบ</button>
      </td>
    </tr>`).join("");
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.getElementById("btn-search").addEventListener("click", () => load().catch(alert));
["q", "status", "sort", "dir"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => load().catch(alert));
});
document.getElementById("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") load().catch(alert);
});

document.getElementById("report-rows").addEventListener("click", async (e) => {
  const t = e.target;
  try {
    if (t.dataset.fav) {
      const on = t.dataset.on !== "1";
      await api("/api/reports/" + t.dataset.fav, { method: "PUT", body: JSON.stringify({ is_favorite: on }) });
      await load();
    } else if (t.dataset.dup) {
      const r = await api("/api/reports/" + t.dataset.dup + "/duplicate", { method: "POST", body: "{}" });
      location.href = "/reports/" + r.id + "/edit";
    } else if (t.dataset.del) {
      if (!confirm("ลบรายงานนี้?")) return;
      await api("/api/reports/" + t.dataset.del, { method: "DELETE" });
      await load();
    } else if (t.dataset.pdf) {
      const res = await fetch("/api/reports/" + t.dataset.pdf + "/pdf", { method: "POST", body: "{}" });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || "ส่งออก PDF ไม่ได้");
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "report.pdf";
      a.click();
    }
  } catch (err) {
    alert(err.message);
  }
});

load().catch((err) => {
  document.getElementById("report-rows").innerHTML =
    `<tr><td colspan="7" class="error">${esc(err.message)}</td></tr>`;
});
