document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-disable-on-click]");
  if (!button) {
    return;
  }
  const busyLabel = button.getAttribute("data-busy-label") || "处理中";
  button.dataset.originalLabel = button.textContent.trim();
  button.textContent = busyLabel;
  button.setAttribute("aria-busy", "true");
  button.setAttribute("disabled", "disabled");
});
