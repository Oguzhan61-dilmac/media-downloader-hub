import os
import sys
import shutil
import subprocess
import re
import requests
from typing import List, Dict, Any, Optional, Callable

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


def get_ffmpeg_executable() -> Optional[str]:
    """Returns path to usable ffmpeg executable (system PATH or imageio-ffmpeg fallback)."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return None


def format_timestamp(seconds: float) -> str:
    """Formats float seconds into SRT timestamp: HH:MM:SS,mmm"""
    if seconds is None or seconds < 0:
        seconds = 0.0

    total_millis = int(round(seconds * 1000))
    hours = total_millis // (3600 * 1000)
    rem = total_millis % (3600 * 1000)
    minutes = rem // (60 * 1000)
    rem %= (60 * 1000)
    secs = rem // 1000
    millis = rem % 1000

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def wrap_subtitle_text(text: str, max_chars_per_line: int = 25, max_lines: int = 2) -> str:
    """
    Wraps text into strictly max 1-2 short lines (max ~25 chars/line).
    Never allows 3+ lines on screen.
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    words = cleaned.split()
    if not words:
        return ""

    lines = []
    current_line = []
    current_len = 0

    for word in words:
        word_len = len(word)
        added_len = word_len + (1 if current_line else 0)

        if current_len + added_len <= max_chars_per_line:
            current_line.append(word)
            current_len += added_len
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_len = word_len

    if current_line:
        lines.append(" ".join(current_line))

    # If more than max_lines, force split words into balanced two-line format
    if len(lines) > max_lines:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])
        return f"{line1}\n{line2}"

    return "\n".join(lines)


def split_text_into_short_chunks(
    start_time: float,
    end_time: float,
    text: str,
    max_words: int = 5,
    max_chars_per_line: int = 25,
    max_lines: int = 2
) -> List[Dict[str, Any]]:
    """
    Splits a segment into small time chunks of max 4-5 words (~25 chars/line, max 2 lines).
    Interpolates start and end timestamps so subtitles rhythmically display in short blocks.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    words = cleaned.split()
    if not words:
        return []

    if len(words) <= max_words and len(cleaned) <= (max_chars_per_line * max_lines):
        return [{
            "start": float(start_time),
            "end": float(max(end_time, start_time + 0.6)),
            "text": cleaned
        }]

    # Group words into small chunks of max 4-5 words
    chunk_groups = []
    curr_group = []
    curr_len = 0

    for w in words:
        added_len = len(w) + (1 if curr_group else 0)
        if len(curr_group) >= max_words or (curr_len + added_len > (max_chars_per_line * max_lines)):
            if curr_group:
                chunk_groups.append(curr_group)
            curr_group = [w]
            curr_len = len(w)
        else:
            curr_group.append(w)
            curr_len += added_len

    if curr_group:
        chunk_groups.append(curr_group)

    total_words = len(words)
    total_duration = max(0.6, end_time - start_time)

    result_chunks = []
    word_cursor = 0

    for group in chunk_groups:
        group_len = len(group)
        t_start = start_time + (word_cursor / total_words) * total_duration
        word_cursor += group_len
        t_end = start_time + (word_cursor / total_words) * total_duration
        if t_end <= t_start:
            t_end = t_start + 0.5

        c_text = " ".join(group)
        result_chunks.append({
            "start": round(t_start, 2),
            "end": round(t_end, 2),
            "text": c_text
        })

    return result_chunks


def generate_srt(segments: List[Dict[str, Any]]) -> str:
    """
    Generates standard SRT file string.
    Processes all segments through short-chunk splitting to guarantee strictly max 1-2 short lines per block.
    """
    all_chunks = []
    for seg in segments:
        s_start = float(seg.get("start", 0.0))
        s_end = float(seg.get("end", 0.0))
        raw_text = str(seg.get("text", "")).strip()
        if not raw_text:
            continue

        chunks = split_text_into_short_chunks(s_start, s_end, raw_text, max_words=5, max_chars_per_line=25, max_lines=2)
        all_chunks.extend(chunks)

    blocks = []
    for idx, chunk in enumerate(all_chunks, start=1):
        start_str = format_timestamp(chunk.get("start", 0.0))
        end_str = format_timestamp(chunk.get("end", 0.0))
        raw_text = str(chunk.get("text", "")).strip()

        if not raw_text:
            continue

        wrapped_text = wrap_subtitle_text(raw_text, max_chars_per_line=25, max_lines=2)
        blocks.append(f"{idx}\n{start_str} --> {end_str}\n{wrapped_text}\n")

    return "\n".join(blocks)


def translate_text_free(text: str, source_lang: str, target_lang: str) -> str:
    """Translates single text string using deep_translator or free Google API fallback."""
    if not text or not text.strip():
        return ""

    src = "auto" if source_lang in ("auto", "") else source_lang
    tgt = target_lang if target_lang else "tr"

    if GoogleTranslator is not None:
        try:
            res = GoogleTranslator(source=src, target=tgt).translate(text)
            if res:
                return res
        except Exception:
            pass

    # Free web REST fallback
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={src}&tl={tgt}&dt=t&q={requests.utils.quote(text)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return "".join([item[0] for item in data[0] if item[0]])
    except Exception:
        pass

    return text


def escape_ffmpeg_path(filepath: str) -> str:
    """Escapes path characters for FFmpeg subtitles filter parameter on Windows."""
    clean = filepath.replace("\\", "/")
    if len(clean) >= 2 and clean[1] == ":":
        clean = clean[0] + "\\:" + clean[2:]
    return clean.replace("'", "'\\\\''")


def process_auto_subtitles(
    video_path: str,
    output_dir: str,
    source_lang: str = "ru",
    target_lang: str = "tr",
    progress_callback: Optional[Callable[[int, str, float, str], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Dict[str, str]:
    """
    Automated pipeline:
    1/3: faster-whisper speech recognition (ru -> timestamps & text)
    2/3: Translation (ru -> tr via deep-translator/free fallback)
    3/3: FFmpeg Hardsub rendering ([video_title]_altyazili.mp4)
    """
    def _log(msg: str):
        if log_callback:
            try:
                log_callback(str(msg))
            except Exception:
                pass

    def _is_cancelled() -> bool:
        return bool(cancel_check and cancel_check())

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

    base_title = os.path.splitext(os.path.basename(video_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    srt_path = os.path.join(output_dir, f"{base_title}_{target_lang}.srt")
    subtitled_video_path = os.path.join(output_dir, f"{base_title}_altyazili.mp4")

    # STEP 1: Speech-to-Text Transcription via faster-whisper (1/3)
    _log("=" * 50)
    _log(f"OTOMATİK ALTYAZI MODÜLÜ BAŞLATILDI: {base_title}")
    _log("Adım 1/3: Ses konuşmaları ve zaman kodları çıkarılıyor (Whisper)...")

    if progress_callback:
        progress_callback(1, "1/3 Ses transkript ediliyor (Whisper)...", 0.0, "Yapay zeka modeli hazırlanıyor...")

    if WhisperModel is None:
        raise RuntimeError("faster-whisper kütüphanesi yüklenemedi. Lütfen 'pip install faster-whisper' çalıştırın.")

    model = None
    try:
        import torch
        if torch.cuda.is_available():
            _log("Whisper Modeli: GPU (CUDA) deneniyor...")
            model = WhisperModel("base", device="cuda", compute_type="float16")
    except Exception as cuda_ex:
        _log(f"[!] CUDA GPU başlatılamadı ({cuda_ex}). CPU moduna geçiliyor...")
        model = None

    if model is None:
        _log("Whisper Modeli: CPU (int8) modunda yükleniyor...")
        try:
            model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception as cpu_ex:
            raise RuntimeError(f"Whisper modeli yüklenirken hata oluştu: {cpu_ex}")

    lang_code = None if source_lang in ("auto", "", None) else source_lang

    _log("Konuşma parçaları analiz ediliyor (Whisper - Kelime Seviyeli Zamanlama)...")
    try:
        segments_gen, info = model.transcribe(
            video_path,
            language=lang_code,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True
        )
        segments_list = list(segments_gen)
    except Exception as vad_ex:
        _log(f"[!] VAD filtresi yüklenemedi ({vad_ex}). VAD filtresiz transkripsiyon moduna geçiliyor...")
        segments_gen, info = model.transcribe(
            video_path,
            language=lang_code,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False
        )
        segments_list = list(segments_gen)

    total_sec = info.duration if info and info.duration > 0 else 0.0
    _log(f"Algılanan Konuşma Dili: {info.language.upper()} (Olasılık: %{info.language_probability * 100:.1f})")

    extracted_segments = []
    for seg in segments_list:
        if _is_cancelled():
            raise RuntimeError("İşlem kullanıcı tarafından iptal edildi.")

        text_clean = seg.text.strip()
        if text_clean:
            extracted_segments.append({
                "start": float(seg.start),
                "end": float(seg.end),
                "text": text_clean
            })

        if total_sec > 0:
            pct = min(100.0, (seg.end / total_sec) * 100.0)
            if progress_callback:
                progress_callback(1, "1/3 Ses transkript ediliyor (Whisper)...", pct, f"%{pct:.0f} ({seg.end:.0f}s / {total_sec:.0f}s)")

    if not extracted_segments:
        _log("UYARI: Videoda herhangi bir ses veya konuşma tespit edilemedi.")
        return {"srt": "", "video": video_path}

    _log(f"1/3 Başarılı: {len(extracted_segments)} konuşma segmenti çıkarıldı.")

    if _is_cancelled():
        raise RuntimeError("İşlem kullanıcı tarafından iptal edildi.")

    # STEP 2: Translation to Target Language (2/3)
    effective_src = info.language if (source_lang in ("auto", "", None) and info and info.language) else source_lang
    _log(f"Adım 2/3: Metinler hedef dile ({target_lang.upper()}) çevriliyor...")

    if progress_callback:
        progress_callback(2, f"2/3 {target_lang.upper()} diline çevriliyor...", 0.0, "Çeviri hazırlanıyor...")

    total_count = len(extracted_segments)
    translated_segments = []

    # If source language and target language are identical, bypass translation API calls
    if effective_src and effective_src.lower() == target_lang.lower():
        _log(f"Kaynak dil ({effective_src.upper()}) ve hedef dil ({target_lang.upper()}) aynı. Çeviri adımı atlanıyor, orijinal transkript kullanılıyor.")
        translated_segments = [dict(seg) for seg in extracted_segments]
        if progress_callback:
            progress_callback(2, f"2/3 {target_lang.upper()} diline çevriliyor...", 100.0, "Kaynak ve hedef dil aynı, orijinal metin kullanıldı.")
    else:
        for i, item in enumerate(extracted_segments, start=1):
            if _is_cancelled():
                raise RuntimeError("İşlem kullanıcı tarafından iptal edildi.")

            raw = item["text"]
            translated_txt = translate_text_free(raw, effective_src, target_lang)

            translated_segments.append({
                "start": item["start"],
                "end": item["end"],
                "text": translated_txt
            })

            pct = (i / total_count) * 100.0
            if progress_callback:
                progress_callback(2, f"2/3 {target_lang.upper()} diline çevriliyor...", pct, f"Çevrilen: {i}/{total_count} (%{pct:.0f})")

    # Save SRT File
    srt_content = generate_srt(translated_segments)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    _log(f"2/3 Başarılı: SRT altyazı dosyası kaydedildi -> {os.path.basename(srt_path)}")

    if _is_cancelled():
        raise RuntimeError("İşlem kullanıcı tarafından iptal edildi.")

    # STEP 3: Burn Subtitles to Video via FFmpeg (3/3)
    _log("Adım 3/3: Altyazı videoya gömülüyor (FFmpeg Shorts/Mobile Hardsub Stili)...")
    if progress_callback:
        progress_callback(3, "3/3 Altyazı videoya gömülüyor...", 0.0, "FFmpeg video render başlatılıyor...")

    ffmpeg_exe = get_ffmpeg_executable()
    if not ffmpeg_exe:
        _log("[HATA] FFmpeg sistemde veya imageio kütüphanesinde bulunamadı. Hardsub gömme atlandı, sadece .srt altyazı oluşturuldu.")
        return {"srt": srt_path, "video": video_path}

    _log(f"Kullanılan FFmpeg Çalıştırıcısı: {ffmpeg_exe}")
    escaped_srt = escape_ffmpeg_path(os.path.abspath(srt_path))

    # Shorts/Mobile Subtitle Standard ASS force_style with 1080x1920 reference resolution:
    # PlayResX=1080, PlayResY=1920, FontName=Arial, FontSize=42, Alignment=2 (Bottom Center), MarginV=120 (safe bottom zone),
    # PrimaryColour=&H0000FFFF (Yellow), OutlineColour=&H00000000 (Black Outline), BorderStyle=1, Outline=3, Shadow=1.5
    force_style = (
        "PlayResX=1080,"
        "PlayResY=1920,"
        "FontName=Arial,"
        "FontSize=42,"
        "Alignment=2,"
        "MarginV=120,"
        "PrimaryColour=&H0000FFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=3,"
        "Shadow=1.5"
    )
    vf_filter = f"subtitles='{escaped_srt}':force_style='{force_style}'"

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", video_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        subtitled_video_path
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        encoding="utf-8",
        errors="ignore"
    )

    time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
    duration_regex = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")
    render_total_sec = 0.0

    while True:
        if _is_cancelled():
            proc.kill()
            raise RuntimeError("İşlem kullanıcı tarafından iptal edildi.")

        line = proc.stderr.readline()
        if not line and proc.poll() is not None:
            break

        if line:
            if render_total_sec == 0.0:
                m_dur = duration_regex.search(line)
                if m_dur:
                    h, m, s = m_dur.groups()
                    render_total_sec = int(h) * 3600 + int(m) * 60 + float(s)

            m_time = time_regex.search(line)
            if m_time and render_total_sec > 0:
                h, m, s = m_time.groups()
                curr_sec = int(h) * 3600 + int(m) * 60 + float(s)
                pct = min(100.0, (curr_sec / render_total_sec) * 100.0)
                if progress_callback:
                    progress_callback(3, "3/3 Altyazı videoya gömülüyor (FFmpeg)...", pct, f"Render: %{pct:.0f} ({curr_sec:.0f}s / {render_total_sec:.0f}s)")

    retcode = proc.wait()
    if retcode != 0:
        _log(f"[HATA] FFmpeg render hatası verdi (Exit Code: {retcode}). SRT dosyası korundu.")
        return {"srt": srt_path, "video": video_path}

    _log(f"3/3 Başarılı: Altyazılı video oluşturuldu -> {os.path.basename(subtitled_video_path)}")
    _log("=" * 50)

    return {"srt": srt_path, "video": subtitled_video_path}
