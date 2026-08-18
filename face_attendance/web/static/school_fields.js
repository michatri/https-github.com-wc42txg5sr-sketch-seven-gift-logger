/* Shared helpers for year/term/grade/room selects */

window.SchoolFields = {
  ADD_YEAR: "__add_year__",
  ADD_ROOM: "__add_room__",

  escapeHtml(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  },

  fillSelect(selectEl, values, opts = {}) {
    if (!selectEl) return;
    const {
      includeEmpty = true,
      emptyLabel = "เลือก",
      selected = "",
      addValue = null,
      addLabel = null,
    } = opts;
    const cur = selected || selectEl.value || "";
    const parts = [];
    if (includeEmpty) {
      parts.push(`<option value="">${this.escapeHtml(emptyLabel)}</option>`);
    }
    (values || []).forEach((v) => {
      parts.push(
        `<option value="${this.escapeHtml(v)}">${this.escapeHtml(v)}</option>`
      );
    });
    if (addValue && addLabel) {
      parts.push(
        `<option value="${this.escapeHtml(addValue)}">${this.escapeHtml(addLabel)}</option>`
      );
    }
    selectEl.innerHTML = parts.join("");
    if (cur && [...selectEl.options].some((o) => o.value === cur)) {
      selectEl.value = cur;
    } else {
      selectEl.value = "";
    }
  },

  async loadOptions() {
    const res = await fetch("/api/school-options");
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "โหลดตัวเลือกไม่สำเร็จ");
    return data.options;
  },

  async fillProfileSelects(prefix = "", options = null, selected = {}) {
    const opts = options || (await this.loadOptions());
    const id = (name) => document.getElementById(prefix + name);
    this.fillSelect(id("academic_year"), opts.academic_year, {
      emptyLabel: "เลือกปีการศึกษา",
      selected: selected.academic_year || "",
      addValue: this.ADD_YEAR,
      addLabel: "+ เพิ่มปีการศึกษา",
    });
    this.fillSelect(id("term"), opts.term, {
      emptyLabel: "เลือกเทอม",
      selected: selected.term || "",
    });
    this.fillSelect(id("grade"), opts.grade, {
      emptyLabel: "เลือกชั้น",
      selected: selected.grade || "",
    });
    this.fillSelect(id("room"), opts.room, {
      emptyLabel: "เลือกห้อง",
      selected: selected.room || "",
      addValue: this.ADD_ROOM,
      addLabel: "+ เพิ่มห้อง",
    });
    return opts;
  },

  bindAddHandlers(prefix = "", onChanged = null) {
    const yearEl = document.getElementById(prefix + "academic_year");
    const roomEl = document.getElementById(prefix + "room");

    const handleYear = async () => {
      if (!yearEl || yearEl.value !== this.ADD_YEAR) return;
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
      await this.fillProfileSelects(prefix, data.options, {
        academic_year: value.trim(),
        term: document.getElementById(prefix + "term")?.value || "",
        grade: document.getElementById(prefix + "grade")?.value || "",
        room: document.getElementById(prefix + "room")?.value || "",
      });
      if (onChanged) onChanged(data.options);
    };

    const handleRoom = async () => {
      if (!roomEl || roomEl.value !== this.ADD_ROOM) return;
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
      await this.fillProfileSelects(prefix, data.options, {
        academic_year: document.getElementById(prefix + "academic_year")?.value || "",
        term: document.getElementById(prefix + "term")?.value || "",
        grade: document.getElementById(prefix + "grade")?.value || "",
        room: value.trim(),
      });
      if (onChanged) onChanged(data.options);
    };

    if (yearEl && !yearEl.dataset.addBound) {
      yearEl.addEventListener("change", handleYear);
      yearEl.dataset.addBound = "1";
    }
    if (roomEl && !roomEl.dataset.addBound) {
      roomEl.addEventListener("change", handleRoom);
      roomEl.dataset.addBound = "1";
    }
  },
};
