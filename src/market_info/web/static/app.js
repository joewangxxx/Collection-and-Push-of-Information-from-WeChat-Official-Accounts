document.addEventListener("submit", (event) => {
  const form = event.target;
  const submitter = event.submitter;
  const button = submitter?.matches("[data-disable-on-click]")
    ? submitter
    : form.querySelector("[data-disable-on-click]");
  if (!button) {
    return;
  }
  const busyLabel = button.getAttribute("data-busy-label") || "处理中";
  button.dataset.originalLabel = button.textContent.trim();
  button.textContent = busyLabel;
  button.setAttribute("aria-busy", "true");
  window.requestAnimationFrame(() => {
    button.setAttribute("disabled", "disabled");
  });
});
