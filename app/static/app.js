function wireConfirmForms() {
  /** @type {NodeListOf<HTMLFormElement>} */
  const forms = document.querySelectorAll("form[data-confirm]");
  for (const form of forms) {
    if (form.dataset.confirmWired === "1") continue;
    form.dataset.confirmWired = "1";
    form.addEventListener("submit", (e) => {
      const msg = form.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(msg)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", wireConfirmForms);
} else {
  wireConfirmForms();
}

