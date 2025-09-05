// Basic JS placeholder (fetch helpers, debounce, etc.)

function debounce(fn, delay = 300) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), delay);
  };
}

async function ping(url = "/health") {
  try {
    const res = await fetch(url);
    console.log("Ping", url, await res.json());
  } catch (e) {
    console.warn("Ping failed", e);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  ping("/health");
});
