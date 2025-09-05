// минимальная обёртка над fetch с CSRF и JSON-ошибками
const api = (() => {
  let csrf = null;
  async function ensureCsrf() {
    if (csrf) return csrf;
    const r = await fetch("/api/v1/csrf");
    const js = await r.json();
    csrf = js.csrf;
    return csrf;
  }
  async function j(method, url, body) {
    await ensureCsrf();
    const r = await fetch(url, {
      method,
      headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
      body: body ? JSON.stringify(body) : undefined,
      credentials: "same-origin"
    });
    const txt = await r.text();
    const js = txt ? JSON.parse(txt) : {};
    if (!r.ok) throw Object.assign(new Error("HTTP "+r.status), {response: js, status: r.status});
    return js;
  }
  return {
    get: (u) => j("GET", u),
    post: (u, b) => j("POST", u, b),
    put: (u, b) => j("PUT", u, b),
    del: (u) => j("DELETE", u),
  };
})();
