(() => {
  const gameListEl = document.getElementById("gameList");
  const emptyHint = document.getElementById("emptyHint");
  const previewEmpty = document.getElementById("previewEmpty");
  const previewContent = document.getElementById("previewContent");
  const previewIcon = document.getElementById("previewIcon");
  const previewIconFallback = document.getElementById("previewIconFallback");
  const previewTitle = document.getElementById("previewTitle");
  const previewDesc = document.getElementById("previewDesc");
  const playBtn = document.getElementById("playBtn");
  const playHint = document.getElementById("playHint");
  const libraryInfo = document.getElementById("libraryInfo");

  /** @type {Array<any>} */
  let games = [];
  let selectedId = null;

  function initials(name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  function renderList() {
    gameListEl.innerHTML = "";
    if (!games.length) {
      emptyHint.classList.remove("hidden");
      previewEmpty.classList.remove("hidden");
      previewContent.classList.add("hidden");
      libraryInfo.textContent = "Library: 0 games";
      return;
    }
    emptyHint.classList.add("hidden");
    libraryInfo.textContent = `Library: ${games.length} game${
      games.length === 1 ? "" : "s"
    }`;

    games.forEach((g) => {
      const li = document.createElement("li");
      li.className = "game-item";
      li.dataset.id = g.id;
      if (g.id === selectedId) li.classList.add("is-selected");

      if (g.iconDataUrl) {
        const img = document.createElement("img");
        img.className = "game-item__icon";
        img.src = g.iconDataUrl;
        img.alt = "";
        li.appendChild(img);
      } else {
        const div = document.createElement("div");
        div.className = "game-item__icon game-item__icon--empty";
        div.textContent = initials(g.name);
        li.appendChild(div);
      }

      const span = document.createElement("span");
      span.className = "game-item__name";
      span.textContent = g.name;
      li.appendChild(span);

      li.addEventListener("click", () => selectGame(g.id));
      gameListEl.appendChild(li);
    });
  }

  function selectGame(id) {
    selectedId = id;
    document.querySelectorAll(".game-item").forEach((el) => {
      el.classList.toggle("is-selected", el.dataset.id === id);
    });

    const g = games.find((x) => x.id === id);
    if (!g) return;

    previewEmpty.classList.add("hidden");
    previewContent.classList.remove("hidden");
    playHint.classList.add("hidden");

    previewTitle.textContent = g.name;
    previewDesc.textContent = g.description;

    if (g.iconDataUrl) {
      previewIcon.src = g.iconDataUrl;
      previewIcon.classList.remove("hidden");
      previewIconFallback.classList.add("hidden");
    } else {
      previewIcon.classList.add("hidden");
      previewIconFallback.classList.remove("hidden");
      previewIconFallback.textContent = initials(g.name);
    }

    if (!g.hasExecutable) {
      playHint.textContent =
        "Add a .exe or launch.bat in this game’s folder on your USB.";
      playHint.classList.remove("hidden");
    }
  }

  playBtn.addEventListener("click", async () => {
    const g = games.find((x) => x.id === selectedId);
    if (!g) return;
    if (!g.exePath) {
      playHint.textContent = "No .exe or launch.bat found in this game folder.";
      playHint.classList.remove("hidden");
      return;
    }
    const r = await window.usbGames.launchGame(g.exePath, g.launchKind);
    if (!r.ok) {
      playHint.textContent = r.message || "Could not launch.";
      playHint.classList.remove("hidden");
    }
  });

  document.getElementById("btnOpenFolder").addEventListener("click", () => {
    window.usbGames.openGamesFolder();
  });

  document.getElementById("btnRefresh").addEventListener("click", () => {
    load();
  });

  async function load() {
    const res = await window.usbGames.scanGames();
    games = res.games || [];
    document.getElementById("usbStatus").textContent = "USB: Connected";
    if (res.error) {
      emptyHint.textContent = res.error;
      emptyHint.classList.remove("hidden");
    }
    renderList();
    if (games.length) {
      const still = games.some((g) => g.id === selectedId);
      if (!still) selectedId = games[0].id;
      selectGame(selectedId);
    } else {
      selectedId = null;
      previewEmpty.classList.remove("hidden");
      previewContent.classList.add("hidden");
    }
  }

  load();
})();
