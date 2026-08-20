document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (!tab) return;
  const group = tab.dataset.group || "main";
  document.querySelectorAll(`[data-tab][data-group="${group}"]`).forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(`[data-pane][data-group="${group}"]`).forEach((p) => p.classList.remove("active"));
  tab.classList.add("active");
  const pane = document.querySelector(`[data-pane="${tab.dataset.tab}"][data-group="${group}"]`);
  if (pane) pane.classList.add("active");
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (e) => {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  });
});
