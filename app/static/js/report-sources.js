async function api(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || "โหลดแหล่งข้อมูลไม่ได้");
  return data;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

(async () => {
  const root = document.getElementById("source-root");
  try {
    const sources = await api("/api/data-sources");
    const src = (sources.items || [])[0];
    if (!src) {
      root.textContent = "ยังไม่มีแหล่งข้อมูล";
      return;
    }
    const cat = await api("/api/data-sources/" + src.id + "/tables");
    const relHtml = (cat.relationships || []).map((r) =>
      `<li>${esc(r.label)} <span class="muted">(${esc(r.source)})</span></li>`
    ).join("");
    root.innerHTML = `
      <h3>${esc(src.name)}</h3>
      <p class="muted">${esc(src.description || "")}</p>
      <p>อะแดปเตอร์: <code>${esc(src.adapter)}</code> — การเข้าถึงผ่านแบ็กเอนด์เท่านั้น</p>
      ${(cat.tables || []).map((t) => `
        <h3>${esc(t.label)} <span class="muted">${esc(t.name)}</span></h3>
        <table class="schema-table">
          <tr><th>คอลัมน์</th><th>ป้าย</th><th>ชนิด</th><th>PK</th><th>FK</th></tr>
          ${(t.columns || []).map((c) => `
            <tr>
              <td><code>${esc(c.name)}</code></td>
              <td>${esc(c.label)}</td>
              <td>${esc(c.type)}</td>
              <td>${c.pk ? "ใช่" : ""}</td>
              <td>${c.fk ? esc(c.fk.table + "." + c.fk.to) : ""}</td>
            </tr>`).join("")}
        </table>
      `).join("")}
      <h3>ความสัมพันธ์</h3>
      <ul>${relHtml || "<li class='muted'>ไม่พบ foreign key ในฐานข้อมูล</li>"}</ul>
    `;
  } catch (err) {
    root.innerHTML = `<div class="error">${esc(err.message)}</div>`;
  }
})();
