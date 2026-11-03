(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("form");
  const urlInput = $("url");
  const submitBtn = $("submit-btn");
  const formError = $("form-error");
  const progress = $("progress");
  const result = $("result");
  const studio = $("studio");
  const autoSub = $("auto_subtitle");
  const subOptions = $("sub-options");
  const autoSplit = $("auto_split");
  const cleanAudio = $("clean_audio");

  const POLL_MS = 1200;
  const STORAGE_KEY = "mdh-task";
  let pollTimer = null;
  let currentTask = null;
  let health = null;
  let turnstileToken = null;
  let turnstileWidget = null;

  // ---------- helpers
  const store = {
    get() { try { return sessionStorage.getItem(STORAGE_KEY); } catch { return null; } },
    set(v) { try { sessionStorage.setItem(STORAGE_KEY, v); } catch { /* private mode */ } },
    clear() { try { sessionStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ } },
  };

  function formatBytes(n) {
    if (!n && n !== 0) return "";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
  }

  function isYouTube(url) {
    try {
      const host = new URL(url).hostname.toLowerCase();
      return ["youtube.com", "youtu.be", "youtube-nocookie.com"].some((h) => host === h || host.endsWith("." + h));
    } catch { return false; }
  }

  function showError(msg) {
    formError.textContent = msg;
    formError.hidden = !msg;
  }

  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.querySelector("span").textContent = busy ? "Hazırlanıyor..." : "İndir";
    form.querySelectorAll("input, select, button.ghost").forEach((el) => { el.disabled = busy; });
    if (!busy) syncStudio();
  }

  function selectedFormat() {
    return form.querySelector('input[name="format"]:checked').value;
  }

  function syncStudio() {
    const mp3 = selectedFormat() === "mp3";
    const subsAllowed = !health || health.limits.subtitles_enabled;
    studio.classList.toggle("disabled", mp3 || !subsAllowed);
    if (mp3 || !subsAllowed) autoSub.checked = false;
    const on = autoSub.checked;
    subOptions.classList.toggle("off", !on);
    subOptions.querySelectorAll("select").forEach((s) => { s.disabled = !on; });
    autoSplit.disabled = !on;
    cleanAudio.disabled = !on;
    if (!on) { autoSplit.checked = false; cleanAudio.checked = false; }
  }

  // ---------- health / limits
  async function loadHealth() {
    try {
      const r = await fetch("/api/health", { cache: "no-store" });
      if (!r.ok) return;
      health = await r.json();
      document.querySelectorAll("[data-limit]").forEach((el) => {
        const v = health.limits[el.dataset.limit];
        if (v !== undefined) el.textContent = v;
      });
      if (health.desktop_app_url) {
        $("desktop-link").href = health.desktop_app_url;
        $("banner-desktop-link").href = health.desktop_app_url;
      }
      $("yt-banner").hidden = !(health.youtube && health.youtube.ok === false);
      if (health.contact_email) {
        document.querySelectorAll("[data-contact]").forEach((a) => {
          a.href = `mailto:${health.contact_email}`;
          a.hidden = false;
        });
      }
      if (health.turnstile_site_key) initTurnstile(health.turnstile_site_key);
      syncStudio();
    } catch { /* site still works without it */ }
  }

  // ---------- bot protection (Cloudflare Turnstile, only when the server enables it)
  function initTurnstile(siteKey) {
    const box = $("turnstile");
    box.hidden = false;
    window.__mdhTurnstileReady = () => {
      turnstileWidget = window.turnstile.render("#turnstile", {
        sitekey: siteKey,
        theme: "dark",
        callback: (token) => { turnstileToken = token; },
        "expired-callback": () => { turnstileToken = null; },
        "error-callback": () => { turnstileToken = null; },
      });
    };
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=__mdhTurnstileReady";
    s.async = true;
    document.head.appendChild(s);
  }

  function resetTurnstile() {
    // tokens are single use
    turnstileToken = null;
    if (window.turnstile && turnstileWidget !== null) {
      try { window.turnstile.reset(turnstileWidget); } catch { /* ignore */ }
    }
  }

  // ---------- progress UI
  function renderStatus(st) {
    $("step-name").textContent = st.step_name || "İşleniyor...";
    let detail = st.detail || "";
    if (st.status === "queued" && st.queue_position) {
      detail = `Sırada ${st.queue_position}. kişisin. Birkaç saniye içinde başlayacak.`;
    }
    $("step-detail").textContent = detail;
    const pct = Math.max(0, Math.min(100, Number(st.progress_pct) || 0));
    $("pct").textContent = `%${Math.round(pct)}`;
    $("bar-fill").style.width = `${pct}%`;
    progress.classList.toggle("indeterminate", st.status === "queued" || (st.status === "processing" && pct === 0));
  }

  function showResult(st) {
    progress.hidden = true;
    result.hidden = false;
    $("result-name").textContent = st.filename || "dosya";
    $("result-size").textContent = st.filesize ? `· ${formatBytes(st.filesize)}` : "";
    const ttl = health ? health.limits.file_ttl_min : 60;
    const note = st.detail && st.detail !== "Dosya indirmeye hazır." ? `${st.detail} ` : "";
    $("result-note").textContent = `${note}Bağlantı ${ttl} dakika geçerli.`;
    const link = $("download-link");
    link.href = `/api/download/${encodeURIComponent(st.task_id)}`;
    link.click(); // start the download right away; the button stays for a second try
  }

  function finish() {
    clearTimeout(pollTimer);
    pollTimer = null;
    currentTask = null;
    store.clear();
    setBusy(false);
  }

  async function poll(taskId) {
    try {
      const r = await fetch(`/api/status/${encodeURIComponent(taskId)}`, { cache: "no-store" });
      if (r.status === 404) {
        progress.hidden = true;
        showError("Bu işlemin süresi dolmuş. Bağlantıyı tekrar gönder.");
        finish();
        return;
      }
      const st = await r.json();
      renderStatus(st);
      if (st.status === "completed") { showResult(st); finish(); return; }
      if (st.status === "failed" || st.status === "cancelled") {
        progress.hidden = true;
        let msg = st.error || "İşlem tamamlanamadı.";
        if (st.status === "failed" && isYouTube(urlInput.value) && /bot|403|YouTube/i.test(msg) && health) {
          msg += "\n\nYouTube için masaüstü uygulamasını deneyebilirsin.";
        }
        showError(st.status === "cancelled" ? "İşlem iptal edildi." : msg);
        finish();
        return;
      }
    } catch {
      $("step-detail").textContent = "Bağlantı koptu, yeniden deneniyor...";
    }
    pollTimer = setTimeout(() => poll(taskId), POLL_MS);
  }

  function track(taskId) {
    currentTask = taskId;
    store.set(taskId);
    result.hidden = true;
    progress.hidden = false;
    renderStatus({ step_name: "Sıraya alındı...", progress_pct: 0, status: "queued" });
    setBusy(true);
    poll(taskId);
  }

  // ---------- actions
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError("");
    const url = urlInput.value.trim();
    if (!/^https?:\/\/\S+$/i.test(url)) {
      showError("Lütfen http:// veya https:// ile başlayan bir video bağlantısı gir.");
      urlInput.focus();
      return;
    }
    if (health && health.turnstile_site_key && !turnstileToken) {
      showError("Lütfen önce robot doğrulamasının tamamlanmasını bekle.");
      return;
    }
    const payload = {
      turnstile_token: turnstileToken,
      url,
      format: selectedFormat(),
      auto_subtitle: autoSub.checked,
      target_lang: $("target_lang").value,
      subtitle_style: $("subtitle_style").value,
      subtitle_position: $("subtitle_position").value,
      auto_split: autoSplit.checked,
      clean_audio: cleanAudio.checked,
    };
    setBusy(true);
    resetTurnstile();
    try {
      const r = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "İstek kabul edilmedi. Bağlantıyı kontrol et.";
        showError(detail);
        setBusy(false);
        return;
      }
      track(data.task_id);
    } catch {
      showError("Sunucuya ulaşılamadı. İnternet bağlantını kontrol edip tekrar dene.");
      setBusy(false);
    }
  });

  $("paste-btn").addEventListener("click", async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) urlInput.value = text;
      urlInput.focus();
    } catch {
      urlInput.focus();
      showError("Tarayıcı panoya erişime izin vermedi. Bağlantıyı kutuya yapıştır (Ctrl+V / uzun bas).");
    }
  });

  $("cancel-btn").addEventListener("click", async () => {
    if (!currentTask) return;
    $("step-name").textContent = "İptal ediliyor...";
    try { await fetch(`/api/cancel/${encodeURIComponent(currentTask)}`, { method: "POST" }); } catch { /* poll will tell */ }
  });

  $("again-btn").addEventListener("click", () => {
    result.hidden = true;
    urlInput.value = "";
    urlInput.focus();
  });

  form.addEventListener("change", syncStudio);
  urlInput.addEventListener("input", () => showError(""));

  // ---------- init
  syncStudio();
  loadHealth();
  const saved = store.get();
  if (saved) track(saved); // page was refreshed while a job was running
})();
