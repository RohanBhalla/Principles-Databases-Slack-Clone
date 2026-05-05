function qs(sel) {
  return document.querySelector(sel);
}

function show(el, on) {
  if (!el) return;
  el.style.display = on ? "" : "none";
}

window.addEventListener("DOMContentLoaded", () => {
  const editBtn = qs("#ws-desc-edit");
  const cancelBtn = qs("#ws-desc-cancel");
  const form = qs("#ws-desc-form");
  const input = qs("#ws-desc-input");
  const text = qs("#ws-desc-text");

  if (!editBtn || !form || !input || !text) return;

  const original = input.value;

  editBtn.addEventListener("click", () => {
    show(form, true);
    show(editBtn, false);
    input.focus();
    input.selectionStart = input.value.length;
    input.selectionEnd = input.value.length;
  });

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      input.value = original;
      show(form, false);
      show(editBtn, true);
    });
  }

  // Confirm before removing a member.
  document.querySelectorAll("form[data-confirm]").forEach((f) => {
    f.addEventListener("submit", (e) => {
      const msg = f.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(msg)) e.preventDefault();
    });
  });
});

