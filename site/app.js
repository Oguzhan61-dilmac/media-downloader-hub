(() => {
  "use strict";

  // Latest Windows build, attached to every GitHub release by .github/workflows/release-windows.yml
  const APP_URL = "https://github.com/Oguzhan61-dilmac/media-downloader-hub/releases/latest/download/MediaDownloaderHub-Windows.exe";

  const $ = (id) => document.getElementById(id);
  const form = $("form");
  const urlInput = $("url");
  const formError = $("form-error");
  const opened = $("opened");

  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (isMobile) $("mobile-banner").hidden = false;

  $("get-app").href = APP_URL;
  document.querySelectorAll("[data-app-link]").forEach((a) => { a.href = APP_URL; });

  function showError(msg) {
    formError.textContent = msg;
    formError.hidden = !msg;
  }

  function validUrl(text) {
    try {
      const u = new URL(text);
      return (u.protocol === "http:" || u.protocol === "https:") && !!u.hostname;
    } catch { return false; }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    showError("");
    const url = urlInput.value.trim();
    if (!validUrl(url)) {
      showError("Lütfen http:// veya https:// ile başlayan bir video bağlantısı gir.");
      urlInput.focus();
      return;
    }
    const format = form.querySelector('input[name="format"]:checked').value;
    const link = `mdhub://download?url=${encodeURIComponent(url)}&format=${encodeURIComponent(format)}`;

    form.dataset.lastLink = link; // also handy for debugging
    opened.hidden = false;
    $("no-app-hint").hidden = true;
    opened.scrollIntoView({ behavior: "smooth", block: "nearest" });

    // If the app isn't installed the browser silently ignores the link;
    // when the page still has focus after a moment, offer the download.
    let left = false;
    const onBlur = () => { left = true; };
    window.addEventListener("blur", onBlur, { once: true });
    window.location.href = link;
    setTimeout(() => {
      window.removeEventListener("blur", onBlur);
      if (!left) $("no-app-hint").hidden = false;
    }, 1800);
  });

  $("paste-btn").addEventListener("click", async () => {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (text) urlInput.value = text;
      urlInput.focus();
    } catch {
      urlInput.focus();
      showError("Tarayıcı panoya erişime izin vermedi. Bağlantıyı kutuya yapıştır (Ctrl+V).");
    }
  });

  $("again-btn").addEventListener("click", () => {
    opened.hidden = true;
    urlInput.value = "";
    urlInput.focus();
  });

  urlInput.addEventListener("input", () => showError(""));
})();
