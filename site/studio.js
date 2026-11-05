// Medya İndir Stüdyo: AI subtitles + Shorts clips, fully in the browser.
// Whisper (Transformers.js, web worker) -> SRT -> FFmpeg.wasm burns subtitles / cuts 9:16 clips.
// Nothing is uploaded: the video never leaves the user's device.
import { FFmpeg } from "./vendor/ffmpeg/index.js";
import { toBlobURL, fetchFile } from "./vendor/ffmpeg-util/index.js";

const CORE_BASE = "https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/esm";
const MAX_MINUTES = 15;

const $ = (id) => document.getElementById(id);
const els = {
  drop: $("drop"), file: $("file"), fileInfo: $("file-info"), preview: $("preview"),
  form: $("studio-form"), start: $("start-btn"), error: $("studio-error"),
  progress: $("studio-progress"), step: $("s-step"), detail: $("s-detail"), pct: $("s-pct"), fill: $("s-fill"),
  cancel: $("s-cancel"), results: $("results"), resultList: $("result-list"), again: $("again"),
};

let videoFile = null;
let videoDuration = 0;
let videoW = 0;
let videoH = 0;
let ffmpeg = null;
let worker = null;
let cancelled = false;
let rejectTranscribe = null;
const objectUrls = [];

// ------------------------------------------------------------------ UI helpers
function showError(msg) {
  els.error.textContent = msg || "";
  els.error.hidden = !msg;
}

function setProgress(step, detail, pct) {
  els.step.textContent = step;
  if (detail !== undefined) els.detail.textContent = detail;
  const indeterminate = pct === null || pct === undefined;
  els.progress.classList.toggle("indeterminate", indeterminate);
  if (!indeterminate) {
    const p = Math.max(0, Math.min(100, pct));
    els.pct.textContent = `%${Math.round(p)}`;
    els.fill.style.width = `${p}%`;
  } else {
    els.pct.textContent = "";
  }
}

function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec / 60), s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function fmtBytes(n) {
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function baseName() {
  return (videoFile?.name || "video").replace(/\.[^.]+$/, "").replace(/[^\p{L}\p{N}\-_ ]/gu, "").trim() || "video";
}

function option(name) {
  const el = els.form.querySelector(`[name="${name}"]:checked`) || els.form.querySelector(`[name="${name}"]`);
  return el ? el.value : "";
}

function busy(on) {
  els.start.disabled = on;
  els.form.querySelectorAll("input, select").forEach((i) => { i.disabled = on; });
  els.progress.hidden = !on;
}

class Cancelled extends Error {}
function checkCancel() { if (cancelled) throw new Cancelled(); }

// ------------------------------------------------------------------ file input
function acceptFile(file) {
  showError("");
  if (!file) return;
  if (!file.type.startsWith("video/") && !/\.(mp4|mov|mkv|webm|m4v)$/i.test(file.name)) {
    showError("Lütfen bir video dosyası seç (MP4, MOV, MKV, WEBM).");
    return;
  }
  videoFile = file;
  objectUrls.forEach((u) => URL.revokeObjectURL(u));
  objectUrls.length = 0;
  const url = URL.createObjectURL(file);
  objectUrls.push(url);
  els.preview.src = url;
  els.preview.hidden = false;
  els.fileInfo.textContent = `${file.name} · ${fmtBytes(file.size)}`;
  els.preview.onloadedmetadata = () => {
    videoDuration = els.preview.duration || 0;
    videoW = els.preview.videoWidth;
    videoH = els.preview.videoHeight;
    els.fileInfo.textContent = `${file.name} · ${fmtBytes(file.size)} · ${fmtTime(videoDuration)} · ${videoW}×${videoH}`;
    if (videoDuration > MAX_MINUTES * 60) {
      showError(`Bu video ${fmtTime(videoDuration)} uzunluğunda. Tarayıcıda en fazla ${MAX_MINUTES} dakikalık videolar işlenebiliyor; daha uzunları için Windows uygulamasını kullan.`);
    }
  };
  els.start.disabled = false;
  els.results.hidden = true;
}

els.file.addEventListener("change", () => acceptFile(els.file.files[0]));
["dragenter", "dragover"].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => els.drop.addEventListener(ev, (e) => { e.preventDefault(); els.drop.classList.remove("over"); }));
els.drop.addEventListener("drop", (e) => acceptFile(e.dataTransfer.files[0]));

// ------------------------------------------------------------------ audio
async function decodeAudio16k(file) {
  const buf = await file.arrayBuffer();
  try {
    const ctx = new AudioContext({ sampleRate: 16000 });
    const audio = await ctx.decodeAudioData(buf.slice(0));
    await ctx.close();
    return mixDown(audio);
  } catch {
    // Some containers/codecs can't be decoded by the browser: extract with FFmpeg instead
    const ff = await getFFmpeg();
    await ff.writeFile("audio_src", new Uint8Array(buf));
    await ff.exec(["-i", "audio_src", "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", "audio.wav"]);
    const wav = await ff.readFile("audio.wav");
    await ff.deleteFile("audio_src");
    const ctx = new AudioContext({ sampleRate: 16000 });
    const audio = await ctx.decodeAudioData(wav.buffer);
    await ctx.close();
    return mixDown(audio);
  }
}

function mixDown(audio) {
  if (audio.numberOfChannels === 1) return audio.getChannelData(0);
  const a = audio.getChannelData(0), b = audio.getChannelData(1);
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = (a[i] + b[i]) / 2;
  return out;
}

// ------------------------------------------------------------------ whisper
function transcribe(audio, model, language, task) {
  return new Promise((resolve, reject) => {
    rejectTranscribe = reject;
    if (!worker) worker = new Worker(new URL("./whisper-worker.js", import.meta.url), { type: "module" });
    const files = {};
    let started = Date.now();
    const timer = setInterval(() => {
      if (els.step.dataset.phase === "asr") {
        els.detail.textContent = `Geçen süre ${fmtTime((Date.now() - started) / 1000)} · Video ${fmtTime(videoDuration)}`;
      }
    }, 1000);
    worker.onmessage = (e) => {
      const m = e.data;
      if (m.type === "download") {
        files[m.file] = m;
        const loaded = Object.values(files).reduce((s, f) => s + f.loaded, 0);
        const total = Object.values(files).reduce((s, f) => s + f.total, 0);
        setProgress("Yapay zekâ modeli indiriliyor (bir kez)", `${fmtBytes(loaded)} / ${fmtBytes(total)}`, total ? (loaded / total) * 100 : null);
      } else if (m.type === "status") {
        if (m.device) { els.step.dataset.phase = "asr"; started = Date.now(); }
        setProgress(m.text, "", null);
      } else if (m.type === "result") {
        clearInterval(timer); els.step.dataset.phase = "";
        resolve(m.chunks);
      } else if (m.type === "error") {
        clearInterval(timer); els.step.dataset.phase = "";
        reject(new Error(m.message));
      }
    };
    worker.onerror = (e) => { clearInterval(timer); reject(new Error(e.message || "Yapay zekâ çalıştırılamadı.")); };
    worker.postMessage({ audio, model, language, task }, [audio.buffer]);
  });
}

// ------------------------------------------------------------------ subtitles
/** Splits Whisper segments into short on-screen pieces (max 5 words), timing proportional to length. */
function shortPieces(segments, upper) {
  const pieces = [];
  for (const seg of segments) {
    const words = seg.text.split(/\s+/).filter(Boolean);
    if (!words.length) continue;
    const start = Number(seg.start) || 0;
    const end = Number.isFinite(seg.end) && seg.end > start ? seg.end : start + Math.max(1.2, words.length * 0.4);
    const groups = [];
    let cur = [];
    for (const w of words) {
      const len = cur.join(" ").length + w.length + 1;
      if (cur.length && (cur.length >= 5 || len > 30)) { groups.push(cur); cur = []; }
      cur.push(w);
    }
    if (cur.length) groups.push(cur);
    const totalChars = groups.reduce((s, g) => s + g.join(" ").length, 0) || 1;
    let t = start;
    for (const g of groups) {
      const text = g.join(" ");
      const dur = (end - start) * (text.length / totalChars);
      pieces.push({ start: t, end: t + dur, text: upper ? toUpper(text) : text });
      t += dur;
    }
  }
  return pieces;
}

/** Turkish text needs the Turkish i/İ rules; other languages the default ones. */
function toUpper(text) {
  return /[çğıöşüÇĞİÖŞÜ]/.test(text) ? text.toLocaleUpperCase("tr-TR") : text.toUpperCase();
}

function srtTime(sec) {
  const ms = Math.max(0, Math.round(sec * 1000));
  const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")},${String(ms % 1000).padStart(3, "0")}`;
}

function toSrt(pieces, offset = 0) {
  return pieces
    .map((p, i) => `${i + 1}\n${srtTime(p.start - offset)} --> ${srtTime(p.end - offset)}\n${p.text}\n`)
    .join("\n");
}

/** ASS style for libass. Sizes are relative to the script resolution (PlayRes). */
function forceStyle(style, position, vertical) {
  const res = vertical ? "PlayResX=1080,PlayResY=1920" : "PlayResX=1920,PlayResY=1080";
  const margin = vertical ? 260 : 70;
  const pos = { bottom: `Alignment=2,MarginV=${margin}`, center: "Alignment=5,MarginV=0", top: `Alignment=8,MarginV=${margin}` }[position]
    || `Alignment=2,MarginV=${margin}`;
  const size = vertical ? 124 : 92;
  const styles = {
    viral: `Fontname=Anton,Fontsize=${size},PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=6,Shadow=3,BackColour=&H80000000`,
    minimal: `Fontname=Anton,Fontsize=${Math.round(size * 0.78)},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=3,Outline=12,Shadow=0`,
    neon: `Fontname=Anton,Fontsize=${size},PrimaryColour=&H00FFFF00,OutlineColour=&H00FF00C8,BorderStyle=1,Outline=5,Shadow=0`,
  };
  return `${res},${pos},${styles[style] || styles.viral},MarginL=60,MarginR=60,WrapStyle=0`;
}

// ------------------------------------------------------------------ ffmpeg
async function getFFmpeg() {
  if (ffmpeg) return ffmpeg;
  setProgress("Video motoru yükleniyor (bir kez, ~30 MB)", "", null);
  const ff = new FFmpeg();
  await ff.load({
    coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, "text/javascript"),
    wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, "application/wasm"),
  });
  const font = await fetchFile(new URL("./fonts/Anton-Regular.ttf", import.meta.url).href);
  await ff.createDir("/fonts");
  await ff.writeFile("/fonts/Anton-Regular.ttf", font);
  ffmpeg = ff;
  return ff;
}

async function runFFmpeg(ff, args, label, from, span) {
  const onProgress = ({ progress }) => {
    if (progress >= 0 && progress <= 1) setProgress(label, undefined, from + progress * span);
  };
  ff.on("progress", onProgress);
  try {
    const code = await ff.exec(args);
    if (code !== 0) throw new Error("Video işlenemedi (FFmpeg hatası).");
  } finally {
    ff.off("progress", onProgress);
  }
}

function videoFilter(vertical, subsFile, style, position) {
  // Shorts: center-crop landscape video to 9:16 and scale to 720x1280.
  // Normal: cap at 1280px wide to keep in-browser encoding fast.
  const geo = vertical
    ? (videoW > videoH * 9 / 16 ? "crop=ih*9/16:ih," : "") + "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280"
    : "scale='min(1280,iw)':-2";
  return `${geo},subtitles=${subsFile}:fontsdir=/fonts:force_style='${forceStyle(style, position, vertical)}'`;
}

/** Natural clip boundaries: 30-60 s, cut between Whisper segments. */
function clipRanges(segments) {
  const ranges = [];
  let start = null;
  for (const seg of segments) {
    if (start === null) start = seg.start;
    const end = seg.end ?? seg.start;
    if (end - start >= 30) {
      ranges.push([start, Math.min(end, start + 60)]);
      start = null;
    }
  }
  const last = segments[segments.length - 1];
  if (start !== null && last && (last.end ?? videoDuration) - start >= 10) ranges.push([start, Math.min(last.end ?? videoDuration, start + 60)]);
  if (!ranges.length) ranges.push([0, Math.min(videoDuration || 60, 60)]);
  return ranges;
}

// ------------------------------------------------------------------ results
function addResult(name, blob, kind) {
  const url = URL.createObjectURL(blob);
  objectUrls.push(url);
  const li = document.createElement("li");
  li.className = "result-item";
  if (kind === "video") {
    const v = document.createElement("video");
    v.src = url; v.controls = true; v.playsInline = true; v.preload = "metadata";
    li.appendChild(v);
  }
  const row = document.createElement("div");
  row.className = "result-row";
  const label = document.createElement("span");
  label.textContent = `${name} · ${fmtBytes(blob.size)}`;
  const a = document.createElement("a");
  a.className = "btn primary small-btn";
  a.href = url; a.download = name; a.textContent = "İndir";
  row.append(label, a);
  li.appendChild(row);
  els.resultList.appendChild(li);
}

// ------------------------------------------------------------------ main flow
els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  if (!videoFile) { showError("Önce bir video seç."); return; }
  if (videoDuration > MAX_MINUTES * 60) { showError(`En fazla ${MAX_MINUTES} dakikalık videolar işlenebiliyor.`); return; }

  const mode = option("mode");
  const style = option("style");
  const position = option("position");
  const model = option("model");
  const language = option("lang") || null;
  const task = option("output_lang") === "en" ? "translate" : "transcribe";

  cancelled = false;
  busy(true);
  els.results.hidden = true;
  els.resultList.innerHTML = "";
  const t0 = Date.now();

  try {
    setProgress("Ses hazırlanıyor...", "", null);
    const audio = await decodeAudio16k(videoFile);
    checkCancel();

    const segments = await transcribe(audio, model, language, task);
    checkCancel();
    if (!segments.length) throw new Error("Videoda konuşma bulunamadı.");

    const pieces = shortPieces(segments, style === "viral");
    const srt = toSrt(pieces);
    addResult(`${baseName()}_altyazi.srt`, new Blob([srt], { type: "application/x-subrip" }), "file");

    if (mode !== "srt") {
      const ff = await getFFmpeg();
      checkCancel();
      await ff.writeFile("input", await fetchFile(videoFile));

      if (mode === "video") {
        await ff.writeFile("subs.srt", srt);
        const vertical = videoH > videoW;
        await runFFmpeg(ff, ["-i", "input", "-vf", videoFilter(vertical, "subs.srt", style, position),
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "128k",
          "-movflags", "+faststart", "out.mp4"], "Altyazı videoya gömülüyor...", 0, 100);
        const data = await ff.readFile("out.mp4");
        await ff.deleteFile("out.mp4");
        addResult(`${baseName()}_altyazili.mp4`, new Blob([data.buffer], { type: "video/mp4" }), "video");
      } else {
        const ranges = clipRanges(segments);
        const zip = new window.JSZip();
        for (let i = 0; i < ranges.length; i++) {
          checkCancel();
          const [a, b] = ranges[i];
          const clipPieces = pieces.filter((p) => p.end > a && p.start < b)
            .map((p) => ({ ...p, start: Math.max(p.start, a), end: Math.min(p.end, b) }));
          await ff.writeFile("clip.srt", toSrt(clipPieces, a));
          const name = `${baseName()}_short_${i + 1}.mp4`;
          await runFFmpeg(ff, ["-ss", a.toFixed(2), "-to", b.toFixed(2), "-i", "input",
            "-vf", videoFilter(true, "clip.srt", style, position),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "clip.mp4"],
            `Shorts klibi ${i + 1}/${ranges.length} hazırlanıyor...`, (i / ranges.length) * 100, 100 / ranges.length);
          const data = await ff.readFile("clip.mp4");
          await ff.deleteFile("clip.mp4");
          const blob = new Blob([data.buffer], { type: "video/mp4" });
          zip.file(name, blob);
          addResult(name, blob, "video");
        }
        if (ranges.length > 1) {
          setProgress("Klipler paketleniyor...", "", null);
          const zipBlob = await zip.generateAsync({ type: "blob" });
          addResult(`${baseName()}_shorts.zip`, zipBlob, "file");
        }
      }
      await ff.deleteFile("input");
    }

    els.results.hidden = false;
    $("result-time").textContent = `Toplam süre: ${fmtTime((Date.now() - t0) / 1000)}`;
    els.results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    if (err instanceof Cancelled || cancelled) {
      showError("İşlem iptal edildi.");
    } else {
      console.error(err);
      showError(`İşlem tamamlanamadı: ${err.message || err}`);
    }
  } finally {
    busy(false);
  }
});

els.cancel.addEventListener("click", () => {
  cancelled = true;
  setProgress("İptal ediliyor...", "", null);
  // Stop running work right away; engines are reloaded on the next run
  if (worker) { worker.terminate(); worker = null; }
  if (rejectTranscribe) { rejectTranscribe(new Cancelled()); rejectTranscribe = null; }
  if (ffmpeg) { try { ffmpeg.terminate(); } catch { /* ignore */ } ffmpeg = null; }
});

els.again.addEventListener("click", () => {
  els.results.hidden = true;
  els.file.value = "";
  els.file.click();
});

// expose for automated checks
window.__studio = { shortPieces, toSrt, forceStyle, clipRanges };
