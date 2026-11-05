// Speech-to-text in the browser with Whisper (Transformers.js). Runs in a Web Worker
// so the page stays responsive. Model files are downloaded once and cached by the browser.
import { pipeline, env } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.5";

env.allowLocalModels = false;

let asr = null;
let loadedModel = null;
let device = "wasm";

async function pickDevice() {
  try {
    if (self.navigator && navigator.gpu) {
      const adapter = await navigator.gpu.requestAdapter();
      if (adapter) return "webgpu";
    }
  } catch { /* fall back to wasm */ }
  return "wasm";
}

async function load(model) {
  if (asr && loadedModel === model) return;
  device = await pickDevice();
  asr = await pipeline("automatic-speech-recognition", model, {
    device,
    dtype: device === "webgpu" ? { encoder_model: "fp32", decoder_model_merged: "q4" } : "q8",
    progress_callback: (p) => {
      if (p.status === "progress" && p.total) {
        self.postMessage({ type: "download", file: p.file, loaded: p.loaded, total: p.total });
      }
    },
  });
  loadedModel = model;
}

self.onmessage = async (e) => {
  const { audio, model, language, task } = e.data;
  try {
    self.postMessage({ type: "status", text: "Yapay zekâ modeli yükleniyor..." });
    await load(model);
    self.postMessage({ type: "status", text: `Konuşmalar yazıya dökülüyor (${device === "webgpu" ? "GPU" : "CPU"})...`, device });

    const opts = {
      return_timestamps: true,
      chunk_length_s: 30,
      stride_length_s: 5,
      task: task || "transcribe",
    };
    if (language) opts.language = language;

    const out = await asr(audio, opts);
    const chunks = (out.chunks || [])
      .map((c) => ({ start: c.timestamp[0] ?? 0, end: c.timestamp[1], text: (c.text || "").trim() }))
      .filter((c) => c.text);
    self.postMessage({ type: "result", chunks, text: out.text || "" });
  } catch (err) {
    self.postMessage({ type: "error", message: String((err && err.message) || err) });
  }
};
