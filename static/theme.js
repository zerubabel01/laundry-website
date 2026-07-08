// ------------------------------
// Theme toggle logic
// ------------------------------
// The theme choice is saved in localStorage, so it's remembered
// next time this browser visits the site.

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    updateToggleIcon(theme);
}

function updateToggleIcon(theme) {
    const btn = document.getElementById("theme-toggle");
    if (btn) {
        btn.textContent = theme === "dark" ? "☀️" : "🌙";
    }
}

function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    const next = current === "dark" ? "light" : "dark";
    setTheme(next);
}

// When the page finishes loading, wire up the button and fix its icon
document.addEventListener("DOMContentLoaded", function () {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    updateToggleIcon(current);

    const btn = document.getElementById("theme-toggle");
    if (btn) {
        btn.addEventListener("click", toggleTheme);
    }
});