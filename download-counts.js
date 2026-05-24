/**
 * Show download counts beside each .zip download button on the site.
 */
(function () {
  function apiBase() {
    if (typeof window.USBGAMES_API === "string" && window.USBGAMES_API) {
      return window.USBGAMES_API.replace(/\/$/, "");
    }
    var host = (location.hostname || "").toLowerCase();
    if (host === "localhost" || host === "127.0.0.1" || host.endsWith(".onrender.com")) {
      return location.origin.replace(/\/$/, "");
    }
    return "https://usbgames.onrender.com";
  }

  function idFromHref(href) {
    if (!href) return null;
    try {
      var name = href.split("?")[0].split("#")[0].split("/").pop();
      return name && /\.zip$/i.test(name) ? decodeURIComponent(name) : null;
    } catch {
      return null;
    }
  }

  function fmt(n) {
    return Number(n || 0).toLocaleString();
  }

  function applyStats(items) {
    var map = {};
    (items || []).forEach(function (row) {
      map[row.id] = row;
    });

    document.querySelectorAll("a.button[href*='.zip'], a.small[href*='.zip']").forEach(function (link) {
      if (link.dataset.downloadStatsApplied) return;
      var id = idFromHref(link.getAttribute("href"));
      if (!id) return;

      var row = map[id];
      if (!row) return;

      link.dataset.downloadStatsApplied = "1";
      link.dataset.downloadId = id;

      var wrap = document.createElement("div");
      wrap.className = "download-btn-wrap";
      link.parentNode.insertBefore(wrap, link);
      wrap.appendChild(link);

      var stats = document.createElement("span");
      stats.className = "download-stats";
      stats.setAttribute(
        "aria-label",
        fmt(row.total) + " downloads, " + fmt(row.baseline) + " before tracking, " + fmt(row.tracked) + " since"
      );
      stats.innerHTML =
        '<span class="download-stats-total">' +
        fmt(row.total) +
        "</span>" +
        '<span class="download-stats-detail">' +
        fmt(row.baseline) +
        " before · " +
        fmt(row.tracked) +
        " since</span>";
      wrap.appendChild(stats);
    });
  }

  function loadStats() {
    var api = apiBase();
    return fetch(api + "/api/download-stats")
      .then(function (r) {
        if (r.ok) return r.json();
        return fetch("/download-stats.json").then(function (r2) {
          return r2.ok ? r2.json() : Promise.reject();
        });
      })
      .catch(function () {
        return fetch("/download-stats.json").then(function (r) {
          return r.ok ? r.json() : Promise.reject();
        });
      });
  }

  function init() {
    loadStats()
      .then(function (data) {
        applyStats(data.items);
      })
      .catch(function () {
        /* no stats file yet */
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
