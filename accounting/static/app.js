document.querySelectorAll("[data-add-line]").forEach((button) => {
  button.addEventListener("click", () => {
    const kind = button.getAttribute("data-add-line");
    const template = document.getElementById(`${kind}-template`);
    const target = document.getElementById(`${kind}-lines`);
    if (!template || !target) return;
    target.appendChild(template.content.cloneNode(true));
  });
});
