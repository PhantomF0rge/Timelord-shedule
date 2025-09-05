(function () {
  const root = document.documentElement;
  const key = "theme";
  const saved = localStorage.getItem(key);
  if (saved === "dark" || saved === "light") {
    root.setAttribute("data-theme", saved);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.setAttribute("data-theme", "dark");
  }

  const btn = document.getElementById("themeToggle");
  if (btn) {
    btn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem(key, next);
    });
  }
})();

(function () {
  const q = document.getElementById("q");
  const box = document.getElementById("suggest");
  if (!q || !box) return;

  let timer = null;
  const open = () => box.classList.add("open");
  const close = () => box.classList.remove("open");

  const render = (items) => {
    box.innerHTML = items.map(it => `<div class="suggest-item" data-id="${it.id||""}">${it.label||it.name||it.code}</div>`).join("");
    if (items.length) open(); else close();
  };

  q.addEventListener("input", () => {
    const val = q.value.trim();
    clearTimeout(timer);
    if (!val) { close(); return; }
    timer = setTimeout(async () => {
      // сюда подцепим /api/v1/suggest позже
      render([{label:`Демо: «${val}»` }]);
    }, 250);
  });

  document.addEventListener("click", (e) => {
    if (!box.contains(e.target) && e.target !== q) close();
  });

  box.addEventListener("click", (e) => {
    const item = e.target.closest(".suggest-item");
    if (!item) return;
    q.value = item.textContent.trim();
    close();
  });
})();
