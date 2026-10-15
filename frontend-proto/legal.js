/* About and legal page: show the bundled third-party notices. */
fetch("third-party-notices.txt", { cache: "no-store" })
  .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
  .then((t) => { document.getElementById("notices-text").textContent = t; })
  .catch(() => {
    document.getElementById("notices-text").textContent =
      "The notices file ships with the installed app (THIRD-PARTY-NOTICES.txt in the install folder).";
  });
