const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("usbGames", {
  scanGames: () => ipcRenderer.invoke("scan-games"),
  launchGame: (exePath, launchKind) =>
    ipcRenderer.invoke("launch-game", exePath, launchKind),
  openGamesFolder: () => ipcRenderer.invoke("open-games-folder"),
});
