/**
 * UsbGames FAQ — static page. Upload faq.html + faq.js + faq-data.json.
 */
(function () {
  const ADMIN_CODE = "5394";
  const LS_KEY = "usbgames_faq_entries";
  const ADMIN_KEY = "faqStaffUnlocked";

  const BUILTIN_FAQ = [
    {
      id: "install",
      question: "How do I install games on my USB?",
      answer:
        "Download the launcher ZIP or individual game zips, unzip into UsbGames\\PortableGames\\ on your USB stick (keep each game's folder name).",
    },
    {
      id: "payment",
      question: "How do I pay? What currency?",
      answer:
        "Checkout uses PayPal (balance, PayPal account, or card). Prices are in Canadian dollars (CAD). After payment, download links appear on the confirmation page.",
    },
    {
      id: "refund",
      question: "Can I get a refund?",
      answer:
        "See our Refund policy. Contact us with your PayPal receipt if something went wrong with your order.",
    },
    {
      id: "offline",
      question: "Do games need the internet?",
      answer: "No. After games are on your USB, play offline.",
    },
  ];

  let customFaqs = [];

  function randomId() {
    const a = new Uint8Array(8);
    crypto.getRandomValues(a);
    return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
  }

  function normalizeEntry(row) {
    if (!row || !row.question || !row.answer) return null;
    const question = String(row.question).trim();
    const answer = String(row.answer).trim();
    if (question.length < 5 || answer.length < 5) return null;
    return {
      id: row.id || randomId(),
      question,
      answer,
    };
  }

  function normalizeList(rows) {
    const out = [];
    const seen = new Set();
    for (const row of rows || []) {
      const entry = normalizeEntry(row);
      if (!entry || seen.has(entry.id)) continue;
      seen.add(entry.id);
      out.push(entry);
    }
    return out;
  }

  function loadLS() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return [];
      const data = JSON.parse(raw);
      if (Array.isArray(data.faqs)) return normalizeList(data.faqs);
      if (Array.isArray(data.questions)) {
        return normalizeList(
          data.questions
            .filter((q) => q.answer)
            .map((q) => ({ id: q.id, question: q.question, answer: q.answer }))
        );
      }
      return [];
    } catch {
      return [];
    }
  }

  function saveLS() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ faqs: customFaqs }));
    } catch {
      /* ignore */
    }
  }

  function readEmbeddedSeed() {
    const el = document.getElementById("faq-seed-data");
    if (!el) return [];
    try {
      const data = JSON.parse(el.textContent);
      if (Array.isArray(data.faqs)) return normalizeList(data.faqs);
      if (Array.isArray(data.questions)) {
        return normalizeList(
          data.questions
            .filter((q) => q.answer)
            .map((q) => ({ id: q.id, question: q.question, answer: q.answer }))
        );
      }
      return [];
    } catch {
      return [];
    }
  }

  async function fetchJsonFile() {
    try {
      const url = new URL("faq-data.json", window.location.href).href;
      const res = await fetch(url);
      if (!res.ok) return [];
      const data = await res.json();
      if (Array.isArray(data.faqs)) return normalizeList(data.faqs);
      if (Array.isArray(data.questions)) {
        return normalizeList(
          data.questions
            .filter((q) => q.answer)
            .map((q) => ({ id: q.id, question: q.question, answer: q.answer }))
        );
      }
      return [];
    } catch {
      return [];
    }
  }

  function mergeCustom(lists) {
    const byId = new Map();
    for (const list of lists) {
      for (const item of list) {
        byId.set(item.id, item);
      }
    }
    return Array.from(byId.values());
  }

  async function initStore() {
    customFaqs = mergeCustom([readEmbeddedSeed(), await fetchJsonFile(), loadLS()]);
    saveLS();
  }

  function getAllFaqs() {
    const builtinIds = new Set(BUILTIN_FAQ.map((f) => f.id));
    const extra = customFaqs.filter((f) => !builtinIds.has(f.id));
    return [...BUILTIN_FAQ, ...extra];
  }

  function addFaq(question, answer) {
    const q = String(question || "").trim();
    const a = String(answer || "").trim();
    if (q.length < 5) return { ok: false, error: "Question must be at least 5 characters." };
    if (q.length > 300) return { ok: false, error: "Question is too long (max 300 characters)." };
    if (a.length < 5) return { ok: false, error: "Answer must be at least 5 characters." };
    if (a.length > 4000) return { ok: false, error: "Answer is too long (max 4000 characters)." };

    const entry = { id: randomId(), question: q, answer: a };
    customFaqs.push(entry);
    saveLS();
    return { ok: true, message: "FAQ added — visible on the FAQ tab." };
  }

  function unlockStaff(code) {
    if (String(code || "").trim() !== ADMIN_CODE) {
      return { ok: false, error: "Wrong code." };
    }
    try {
      sessionStorage.setItem(ADMIN_KEY, "1");
    } catch {
      /* ignore */
    }
    return { ok: true };
  }

  function isStaff() {
    try {
      return sessionStorage.getItem(ADMIN_KEY) === "1";
    } catch {
      return false;
    }
  }

  function lockStaff() {
    try {
      sessionStorage.removeItem(ADMIN_KEY);
    } catch {
      /* ignore */
    }
  }

  function exportDataJson() {
    const blob = new Blob([JSON.stringify({ faqs: getAllFaqs() }, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "faq-data.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function renderFaqList() {
    const list = document.getElementById("faq-list");
    const empty = document.getElementById("faq-empty");
    if (!list) return;
    const items = getAllFaqs();
    list.innerHTML = "";
    if (!items.length) {
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;
    items.forEach((item) => {
      const details = document.createElement("details");
      details.className = "faq-item";
      const summary = document.createElement("summary");
      summary.textContent = item.question;
      const body = document.createElement("div");
      body.className = "faq-item__answer";
      body.textContent = item.answer;
      details.appendChild(summary);
      details.appendChild(body);
      list.appendChild(details);
    });
  }

  function switchTab(tabId) {
    const tabs = [
      { btn: "tab-faq", panel: "panel-faq" },
      { btn: "tab-new", panel: "panel-new" },
    ];
    tabs.forEach(({ btn, panel }) => {
      const active = btn === tabId;
      const b = document.getElementById(btn);
      const p = document.getElementById(panel);
      if (!b || !p) return;
      b.classList.toggle("faq-tab--active", active);
      b.setAttribute("aria-selected", active ? "true" : "false");
      p.classList.toggle("hidden", !active);
      p.hidden = !active;
    });
    if (tabId === "tab-faq") renderFaqList();
    if (tabId === "tab-new") refreshNewPanel();
  }

  function showNewLocked() {
    const locked = document.getElementById("new-locked");
    const unlocked = document.getElementById("new-unlocked");
    if (locked) {
      locked.classList.remove("hidden");
      locked.hidden = false;
    }
    if (unlocked) {
      unlocked.classList.add("hidden");
      unlocked.hidden = true;
    }
  }

  function showNewUnlocked() {
    const locked = document.getElementById("new-locked");
    const unlocked = document.getElementById("new-unlocked");
    if (locked) {
      locked.classList.add("hidden");
      locked.hidden = true;
    }
    if (unlocked) {
      unlocked.classList.remove("hidden");
      unlocked.hidden = false;
    }
  }

  function refreshNewPanel() {
    if (!isStaff()) {
      showNewLocked();
      return;
    }
    showNewUnlocked();
  }

  function wireEvents() {
    document.getElementById("tab-faq")?.addEventListener("click", () => switchTab("tab-faq"));
    document.getElementById("tab-new")?.addEventListener("click", () => switchTab("tab-new"));

    document.getElementById("new-unlock-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      const err = document.getElementById("new-unlock-error");
      if (err) err.hidden = true;
      const code = document.getElementById("new-code")?.value;
      const res = unlockStaff(code);
      if (!res.ok) {
        if (err) {
          err.textContent = res.error;
          err.hidden = false;
        }
        return;
      }
      const input = document.getElementById("new-code");
      if (input) input.value = "";
      refreshNewPanel();
    });

    document.getElementById("new-faq-form")?.addEventListener("submit", (e) => {
      e.preventDefault();
      const err = document.getElementById("new-faq-error");
      const ok = document.getElementById("new-faq-success");
      if (err) err.hidden = true;
      if (ok) ok.hidden = true;
      const fd = new FormData(e.target);
      const res = addFaq(fd.get("question"), fd.get("answer"));
      if (!res.ok) {
        if (err) {
          err.textContent = res.error;
          err.hidden = false;
        }
        return;
      }
      if (ok) {
        ok.textContent = res.message;
        ok.hidden = false;
      }
      e.target.reset();
      renderFaqList();
    });

    document.getElementById("btn-new-lock")?.addEventListener("click", () => {
      lockStaff();
      showNewLocked();
    });

    document.getElementById("btn-export-faq")?.addEventListener("click", exportDataJson);
  }

  async function boot() {
    try {
      await initStore();
      wireEvents();
      switchTab("tab-faq");
    } catch (err) {
      console.error(err);
      const el = document.getElementById("faq-boot-error");
      if (el) {
        el.textContent = "FAQ failed to load: " + (err.message || err);
        el.hidden = false;
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
