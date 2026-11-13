/* HomenS.AI Error-database · © 2026 Serhii Khomenko · https://homensai.com/ · https://github.com/HomenSAI */
/* Тема до первой отрисовки: выбор посетителя (светлая/тёмная) хранится только в его браузере; иначе — тема системы. */
(function () {
  try {
    var theme = window.localStorage.getItem("hsai-errors-theme");
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) { /* хранилище недоступно — тема системы */ }
})();
