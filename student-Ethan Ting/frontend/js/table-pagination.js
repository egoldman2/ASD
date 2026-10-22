/* Shared pagination for the Accounts and Loyalty tables. Filtering stays local. */
(() => {
  window.createAccountTablePager = (root, render, pageSize = 10) => {
    let page = 0;
    const label = root.dataset.label || "records";
    const summary = document.createElement("p");
    summary.setAttribute("role", "status");
    const controls = document.createElement("div");
    controls.className = "paginationControls";
    const previous = document.createElement("button");
    const next = document.createElement("button");
    for (const [button, text, direction] of [[previous, "Previous", -1], [next, "Next", 1]]) {
      button.type = "button";
      button.className = "secondaryButton";
      button.textContent = text;
      button.setAttribute("aria-label", `${text} page of ${label}`);
      button.addEventListener("click", () => { page += direction; render(); });
      controls.append(button);
    }
    root.replaceChildren(summary, controls);
    previous.disabled = true;
    next.disabled = true;
    controls.hidden = true;
    return {
      reset() { page = 0; },
      slice(items) {
        const lastPage = Math.max(0, Math.ceil(items.length / pageSize) - 1);
        page = Math.max(0, Math.min(page, lastPage));
        const start = page * pageSize;
        summary.textContent = items.length
          ? `Showing ${start + 1} to ${Math.min(start + pageSize, items.length)} of ${items.length} ${label}`
          : `No matching ${label}`;
        previous.disabled = page === 0;
        next.disabled = page === lastPage;
        controls.hidden = items.length <= pageSize;
        return items.slice(start, start + pageSize);
      },
    };
  };
})();
