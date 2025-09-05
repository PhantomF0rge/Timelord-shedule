// Простая обёртка для хранения последней выбранной группы
const TimelordStorage = (() => {
  const KEY = "last_group";
  function getLastGroup() {
    try { return localStorage.getItem(KEY); } catch (_) { return null; }
  }
  function setLastGroup(code) {
    if (!code) return;
    try { localStorage.setItem(KEY, code); } catch (_) {}
  }
  return { getLastGroup, setLastGroup };
})();

// Лёгкий лог, чтобы видеть visitor_id в консоли при разработке
(function () {
  fetch("/health")
    .then(r => r.json())
    .then(j => console.debug("[health]", j))
    .catch(() => {});
})();
