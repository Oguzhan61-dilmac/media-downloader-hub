(() => {
  "use strict";

  // Latest builds, attached to every GitHub release by .github/workflows/release.yml
  const RELEASES = "https://github.com/Oguzhan61-dilmac/media-downloader-hub/releases/latest/download/";
  const WIN_URL = RELEASES + "MedyaIndir-Windows.exe";
  const APK_URL = RELEASES + "MedyaIndir-Android.apk";
  const ANDROID_PACKAGE = "com.mediadownloader.hub.mobile";

  const $ = (id) => document.getElementById(id);
  const form = $("form");
  const urlInput = $("url");
  const formError = $("form-error");
  const opened = $("opened");

  const ua = navigator.userAgent;
  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  if (isIOS) $("mobile-banner").hidden = false;

  const appUrl = isAndroid ? APK_URL : WIN_URL;
  $("get-app").href = appUrl;
  $("get-app").textContent = isAndroid ? "Android uygulamasını indir (APK)" : "Windows uygulamasını indir (ücretsiz)";
  $("apk-hint").hidden = !isAndroid;
  document.querySelectorAll("[data-win-link]").forEach((a) => { a.href = WIN_URL; });
  document.querySelectorAll("[data-android-link]").forEach((a) => { a.href = APK_URL; });

  // The website itself, used as the Android fallback when the app isn't installed
  const here = window.location.href.split("#")[0].split("?")[0];
  if (new URLSearchParams(window.location.search).get("app") === "missing") {
    $("opened").hidden = false;
    $("no-app-hint").hidden = false;
  }

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
    const query = `url=${encodeURIComponent(url)}&format=${encodeURIComponent(format)}`;
    // Android Chrome opens apps through intent:// links and can fall back to a page when the app is missing
    const link = isAndroid
      ? `intent://download?${query}#Intent;scheme=mdhub;package=${ANDROID_PACKAGE};S.browser_fallback_url=${encodeURIComponent(here + "?app=missing")};end`
      : `mdhub://download?${query}`;

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
