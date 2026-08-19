document.querySelectorAll(".entry input[name^='amount_']").forEach((input) => {
  input.addEventListener("blur", () => {
    const raw = input.value.replace(/,/g, "").trim();
    if (!raw) return;
    const n = Number(raw);
    if (!Number.isNaN(n)) input.value = n.toFixed(2);
  });
});
