/* Apply the saved theme before first paint so night/marauder never flash parchment.
   Loaded as a blocking script in <head>; a file rather than inline so the
   Content-Security-Policy can forbid inline scripts. */
try {
  var savedTheme = localStorage.getItem("pensieve-theme");
  if (savedTheme === "night" || savedTheme === "marauder") {
    document.documentElement.setAttribute("data-theme", savedTheme);
  }
} catch (e) { /* storage blocked: stay on day */ }
