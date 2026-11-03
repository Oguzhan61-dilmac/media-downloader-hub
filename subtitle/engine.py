import os
import shutil
import subprocess
import re
import tempfile
import requests
from typing import List, Dict, Any, Optional, Callable, Tuple

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


def chunks_from_words(
    words: List[Dict[str, Any]],
    max_words: int = 5,
    max_chars: int = 50
) -> List[Dict[str, Any]]:
    """
    Groups Whisper word timestamps into short subtitle blocks (max 4-5 words).
    Each block starts on its first word and ends on its last word, so the text
    appears exactly when it is spoken.
    """
    chunks: List[Dict[str, Any]] = []
    group: List[Dict[str, Any]] = []
    group_len = 0
    for w in words:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        added = len(text) + (1 if group else 0)
        if group and (len(group) >= max_words or group_len + added > max_chars):
            chunks.append(group)
            group, group_len = [], 0
            added = len(text)
        group.append({"start": float(w["start"]), "end": float(w["end"]), "word": text})
        group_len += added
    if group:
        chunks.append(group)

    result = []
    for g in chunks:
        start = g[0]["start"]
        end = max(g[-1]["end"], start + 0.4)
        result.append({"start": round(start, 2), "end": round(end, 2), "text": " ".join(x["word"] for x in g)})
    return result


def generate_srt(segments: List[Dict[str, Any]]) -> str:
    """
    Generates standard SRT file string.
    Segments that carry Whisper word timestamps are split on real word timings;
    translated segments (no word timings) are split proportionally.
    Every block is at most 1-2 short lines.
    """
    all_chunks = []
    for seg in segments:
        raw_text = str(seg.get("text", "")).strip()
        if not raw_text:
            continue
        words = seg.get("words")
        if words:
            all_chunks.extend(chunks_from_words(words, max_words=5, max_chars=50))
        else:
            s_start = float(seg.get("start", 0.0))
            s_end = float(seg.get("end", 0.0))
            all_chunks.extend(split_text_into_short_chunks(s_start, s_end, raw_text, max_words=5, max_chars_per_line=25, max_lines=2))

    blocks = []
    idx = 0
    for chunk in all_chunks:
        raw_text = str(chunk.get("text", "")).strip()
        if not raw_text:
            continue
        idx += 1
        start_str = format_timestamp(chunk.get("start", 0.0))
        end_str = format_timestamp(chunk.get("end", 0.0))
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


def build_ass_force_style(style_template: str = "hormozi", position: str = "bottom") -> str:
    """Generates ASS force_style string based on selected template and position."""
    pos_map = {
        "bottom": "Alignment=2,MarginV=120",
        "center": "Alignment=5,MarginV=0",
        "top": "Alignment=8,MarginV=120"
    }
    pos_str = pos_map.get(str(position).lower(), "Alignment=2,MarginV=120")

    style_clean = str(style_template).lower()
    if style_clean == "minimalist":
        style_str = "FontName=Arial,FontSize=38,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=3,Outline=2,Shadow=0"
    elif style_clean == "cyberpunk":
        style_str = "FontName=Arial,FontSize=42,PrimaryColour=&H00FFFF00,OutlineColour=&H00FF007C,BackColour=&H00000000,BorderStyle=1,Outline=4,Shadow=2"
    else:
        # Default: Hormozi / Viral Pop-up (Bold Yellow text, thick black outline)
        style_str = "FontName=Arial,FontSize=44,PrimaryColour=&H0000FFFF,SecondaryColour=&H0000FF00,OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=2"

    return f"PlayResX=1080,PlayResY=1920,{pos_str},{style_str}"



class SubtitleCancelled(RuntimeError):
    """Raised when the user cancels the subtitle pipeline."""


AUDIO_CLEAN_FILTER = "afftdn=nr=12:nf=-25,highpass=f=150,lowpass=f=3500,equalizer=f=1000:width_type=h:width=200:g=3"

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    force_style: str,
    ffmpeg_exe: str,
    clean_audio: bool = False,
    start: Optional[float] = None,
    end: Optional[float] = None,
    progress_callback: Optional[Callable[[float, float, float], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Tuple[bool, str]:
    """
    Burns an SRT file into a video with FFmpeg.

    The subtitles filter has its own escaping rules, and titles containing an
    apostrophe ("Don't Stop") or a Windows drive letter broke them. To avoid
    escaping entirely, the SRT is copied to a temporary folder under a fixed
    ASCII name and FFmpeg runs inside that folder, so the filter only ever sees
    "subtitles=subs.srt". Input/output paths are normal arguments and need no
    escaping.

    Returns (success, last FFmpeg error lines).
    """
    work_dir = tempfile.mkdtemp(prefix="mdh_sub_")
    try:
        shutil.copyfile(srt_path, os.path.join(work_dir, "subs.srt"))
        vf_filter = f"subtitles=subs.srt:force_style='{force_style}'"

        audio_args = ["-c:a", "copy"]
        if clean_audio:
            audio_args = ["-c:a", "aac", "-af", AUDIO_CLEAN_FILTER]

        cmd = [ffmpeg_exe, "-y", "-hide_banner"]
        if start is not None:
            cmd += ["-ss", f"{start:.2f}"]
        if end is not None:
            cmd += ["-to", f"{end:.2f}"]
        cmd += [
            "-i", os.path.abspath(video_path),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-movflags", "+faststart",
        ] + audio_args + [os.path.abspath(output_path)]

        proc = subprocess.Popen(
            cmd,
            cwd=work_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="ignore",
        )

        total_sec = (end - start) if (start is not None and end is not None) else 0.0
        tail: List[str] = []
        while True:
            if cancel_check and cancel_check():
                proc.kill()
                proc.wait()
                raise SubtitleCancelled("İşlem kullanıcı tarafından iptal edildi.")

            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if not line:
                continue

            tail.append(line.rstrip())
            tail = tail[-8:]

            if total_sec <= 0:
                m_dur = _DURATION_RE.search(line)
                if m_dur:
                    h, m, s = m_dur.groups()
                    total_sec = int(h) * 3600 + int(m) * 60 + float(s)

            m_time = _TIME_RE.search(line)
            if m_time and total_sec > 0 and progress_callback:
                h, m, s = m_time.groups()
                curr = int(h) * 3600 + int(m) * 60 + float(s)
                progress_callback(min(100.0, curr / total_sec * 100.0), curr, total_sec)

        ok = proc.wait() == 0 and os.path.exists(output_path)
        return ok, "\n".join(tail)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def split_video_into_clips(
    video_path: str,
    output_dir: str,
    segments: List[Dict[str, Any]],
    ffmpeg_exe: str,
    force_style: str,
    clean_audio: bool = False,
    min_dur: float = 30.0,
    max_dur: float = 60.0,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """
    Splits video into 30-60s clips based on natural Whisper pause boundaries.
    Generates subbed clip MP4s and packages them into a ZIP archive.
    """
    import zipfile

    if not segments:
        return video_path

    base_title = os.path.splitext(os.path.basename(video_path))[0]
    clips_dir = os.path.join(output_dir, f"{base_title}_clips")
    os.makedirs(clips_dir, exist_ok=True)

    clip_ranges = []
    curr_start = segments[0]["start"]
    curr_end = segments[0]["end"]
    clip_segs = [segments[0]]

    for seg in segments[1:]:
        dur = seg["end"] - curr_start
        if dur >= min_dur:
            clip_segs.append(seg)
            curr_end = seg["end"]
            clip_ranges.append((curr_start, curr_end, list(clip_segs)))
            curr_start = seg["end"]
            clip_segs = []
        else:
            clip_segs.append(seg)
            curr_end = seg["end"]

    if clip_segs and (curr_end - curr_start) >= 10.0:
        clip_ranges.append((curr_start, curr_end, list(clip_segs)))

    if not clip_ranges:
        clip_ranges.append((segments[0]["start"], segments[-1]["end"], segments))

    generated_clips = []
    total = len(clip_ranges)
    for idx, (c_start, c_end, c_segs) in enumerate(clip_ranges, start=1):
        if cancel_check and cancel_check():
            raise SubtitleCancelled("İşlem kullanıcı tarafından iptal edildi.")

        adj_segs = []
        for s in c_segs:
            item = {
                "start": max(0.0, s["start"] - c_start),
                "end": max(0.0, s["end"] - c_start),
                "text": s["text"],
            }
            if s.get("words"):
                item["words"] = [
                    {"start": max(0.0, w["start"] - c_start), "end": max(0.0, w["end"] - c_start), "word": w["word"]}
                    for w in s["words"]
                ]
            adj_segs.append(item)

        clip_srt_path = os.path.join(clips_dir, f"klip_{idx}.srt")
        with open(clip_srt_path, "w", encoding="utf-8") as f:
            f.write(generate_srt(adj_segs))

        clip_mp4_path = os.path.join(clips_dir, f"klip_{idx}.mp4")
        ok, err_tail = burn_subtitles(
            video_path, clip_srt_path, clip_mp4_path, force_style, ffmpeg_exe,
            clean_audio=clean_audio, start=c_start, end=c_end, cancel_check=cancel_check,
        )
        if ok:
            generated_clips.append(clip_mp4_path)
        elif log_callback:
            log_callback(f"[!] Klip {idx} oluşturulamadı: {err_tail.splitlines()[-1] if err_tail else 'FFmpeg hatası'}")

        if progress_callback:
            progress_callback(idx / total * 100.0, f"Klip {idx}/{total} hazırlandı")

    if not generated_clips:
        raise RuntimeError("Hiçbir klip oluşturulamadı (FFmpeg hatası).")

    zip_path = os.path.join(output_dir, f"{base_title}_shorts_clips.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for clip in generated_clips:
            zf.write(clip, arcname=os.path.basename(clip))

    if log_callback:
        log_callback(f"[+] Akıllı Shorts Parçalayıcı: {len(generated_clips)} klip üretildi -> {zip_path}")

    return zip_path


def _cuda_available() -> bool:
    """faster-whisper runs on CTranslate2, so ask it directly (torch is not a dependency)."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def load_whisper_model(model_size: str = "base", log: Optional[Callable[[str], None]] = None):
    if WhisperModel is None:
        raise RuntimeError("faster-whisper kütüphanesi yüklenemedi. Lütfen 'pip install faster-whisper' çalıştırın.")
    if _cuda_available():
        try:
            if log:
                log("Whisper Modeli: GPU (CUDA) kullanılıyor...")
            return WhisperModel(model_size, device="cuda", compute_type="float16")
        except Exception as cuda_ex:
            if log:
                log(f"[!] CUDA GPU başlatılamadı ({cuda_ex}). CPU moduna geçiliyor...")
    if log:
        log("Whisper Modeli: CPU (int8) modunda yükleniyor...")
    try:
        return WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as cpu_ex:
        raise RuntimeError(f"Whisper modeli yüklenirken hata oluştu: {cpu_ex}")


def process_auto_subtitles(
    video_path: str,
    output_dir: str,
    source_lang: str = "auto",
    target_lang: str = "tr",
    subtitle_style: str = "hormozi",
    subtitle_position: str = "bottom",
    clean_audio: bool = False,
    auto_split: bool = False,
    progress_callback: Optional[Callable[[int, str, float, str], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """
    Automated pipeline:
    1/3: faster-whisper speech recognition (timestamps & text)
    2/3: Translation (deep-translator / free fallback)
    3/3: FFmpeg hardsub rendering, optional audio denoise and Shorts auto-splitter

    Returns {"srt": path, "video": path, "burned": bool, "note": str}.
    "burned" is False when subtitles could not be put into the video; "video"
    then points to the original file and "note" explains why.
    """
    def _log(msg: str):
        if log_callback:
            try:
                log_callback(str(msg))
            except Exception:
                pass

    def _progress(step: int, name: str, pct: float, detail: str):
        if progress_callback:
            progress_callback(step, name, pct, detail)

    def _check_cancel():
        if cancel_check and cancel_check():
            raise SubtitleCancelled("İşlem kullanıcı tarafından iptal edildi.")

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
    step1 = "1/3 Ses transkript ediliyor (Whisper)..."
    _progress(1, step1, 0.0, "Yapay zeka modeli hazırlanıyor...")

    model = load_whisper_model("base", _log)
    lang_code = None if source_lang in ("auto", "", None) else source_lang

    def _transcribe(vad: bool):
        # transcribe() returns a lazy generator: the real work happens while
        # iterating, so progress is reported per segment as it is decoded.
        segments_gen, info = model.transcribe(
            video_path,
            language=lang_code,
            beam_size=5,
            word_timestamps=True,
            vad_filter=vad,
        )
        total_sec = info.duration if info and info.duration else 0.0
        collected = []
        for seg in segments_gen:
            _check_cancel()
            text_clean = seg.text.strip()
            if text_clean:
                collected.append({
                    "start": float(seg.start),
                    "end": float(seg.end),
                    "text": text_clean,
                    "words": [
                        {"start": float(w.start), "end": float(w.end), "word": w.word}
                        for w in (seg.words or [])
                    ],
                })
            if total_sec > 0:
                pct = min(100.0, (seg.end / total_sec) * 100.0)
                _progress(1, step1, pct, f"%{pct:.0f} ({seg.end:.0f}s / {total_sec:.0f}s)")
        return collected, info

    _log("Konuşma parçaları analiz ediliyor (Whisper - Kelime Seviyeli Zamanlama)...")
    try:
        extracted_segments, info = _transcribe(vad=True)
    except SubtitleCancelled:
        raise
    except Exception as vad_ex:
        _log(f"[!] VAD filtresi ile transkripsiyon başarısız ({vad_ex}). VAD filtresiz deneniyor...")
        extracted_segments, info = _transcribe(vad=False)

    if info and info.language:
        _log(f"Algılanan Konuşma Dili: {info.language.upper()} (Olasılık: %{info.language_probability * 100:.1f})")

    if not extracted_segments:
        _log("UYARI: Videoda herhangi bir ses veya konuşma tespit edilemedi.")
        return {"srt": "", "video": video_path, "burned": False, "note": "Videoda konuşma tespit edilemedi."}

    _log(f"1/3 Başarılı: {len(extracted_segments)} konuşma segmenti çıkarıldı.")
    _check_cancel()

    # STEP 2: Translation to Target Language (2/3)
    effective_src = info.language if (source_lang in ("auto", "", None) and info and info.language) else source_lang
    step2 = f"2/3 {target_lang.upper()} diline çevriliyor..."
    _log(f"Adım 2/3: Metinler hedef dile ({target_lang.upper()}) çevriliyor...")
    _progress(2, step2, 0.0, "Çeviri hazırlanıyor...")

    total_count = len(extracted_segments)
    translated_segments = []

    if effective_src and effective_src.lower() == target_lang.lower():
        _log(f"Kaynak dil ({effective_src.upper()}) ve hedef dil aynı. Orijinal transkript ve kelime zamanlamaları kullanılıyor.")
        translated_segments = [dict(seg) for seg in extracted_segments]
        _progress(2, step2, 100.0, "Kaynak ve hedef dil aynı, orijinal metin kullanıldı.")
    else:
        for i, item in enumerate(extracted_segments, start=1):
            _check_cancel()
            translated_segments.append({
                "start": item["start"],
                "end": item["end"],
                # word timings belong to the source language, so translated text is split proportionally
                "text": translate_text_free(item["text"], effective_src, target_lang),
            })
            pct = (i / total_count) * 100.0
            _progress(2, step2, pct, f"Çevrilen: {i}/{total_count} (%{pct:.0f})")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(generate_srt(translated_segments))
    _log(f"2/3 Başarılı: SRT altyazı dosyası kaydedildi -> {os.path.basename(srt_path)}")
    _check_cancel()

    # STEP 3: Burn Subtitles to Video & Audio Denoise & Auto-Splitter (3/3)
    step3 = "3/3 Altyazı videoya gömülüyor..."
    _log(f"Adım 3/3: Altyazı videoya gömülüyor (Stil: {subtitle_style.upper()}, Konum: {subtitle_position.upper()})...")
    _progress(3, step3, 0.0, "FFmpeg video render başlatılıyor...")

    ffmpeg_exe = get_ffmpeg_executable()
    if not ffmpeg_exe:
        _log("[HATA] FFmpeg bulunamadı. Hardsub gömme atlandı, sadece .srt altyazı oluşturuldu.")
        return {"srt": srt_path, "video": video_path, "burned": False, "note": "FFmpeg bulunamadı, sadece .srt oluşturuldu."}

    force_style = build_ass_force_style(subtitle_style, subtitle_position)
    if clean_audio:
        _log("🔊 FFmpeg ses temizleme (afftdn + voice equalizer) uygulanıyor...")

    if auto_split:
        _log("✂️ Akıllı Shorts Parçalayıcı aktif! 30-60 saniyelik klipler oluşturuluyor...")
        zip_clips_path = split_video_into_clips(
            video_path=video_path,
            output_dir=output_dir,
            segments=translated_segments,
            ffmpeg_exe=ffmpeg_exe,
            force_style=force_style,
            clean_audio=clean_audio,
            log_callback=_log,
            progress_callback=lambda pct, detail: _progress(3, "3/3 Shorts klipleri hazırlanıyor...", pct, detail),
            cancel_check=cancel_check,
        )
        return {"srt": srt_path, "video": zip_clips_path, "burned": True, "note": ""}

    ok, err_tail = burn_subtitles(
        video_path, srt_path, subtitled_video_path, force_style, ffmpeg_exe,
        clean_audio=clean_audio,
        progress_callback=lambda pct, curr, total: _progress(
            3, "3/3 Altyazı videoya gömülüyor (FFmpeg)...", pct, f"Render: %{pct:.0f} ({curr:.0f}s / {total:.0f}s)"
        ),
        cancel_check=cancel_check,
    )
    if not ok:
        last = err_tail.splitlines()[-1] if err_tail else "bilinmeyen hata"
        _log(f"[HATA] FFmpeg render hatası: {last}. SRT dosyası korundu.")
        return {"srt": srt_path, "video": video_path, "burned": False, "note": f"FFmpeg hatası ({last}). Altyazı .srt olarak kaydedildi."}

    _log(f"3/3 Başarılı: Altyazılı video oluşturuldu -> {os.path.basename(subtitled_video_path)}")
    _log("=" * 50)
    return {"srt": srt_path, "video": subtitled_video_path, "burned": True, "note": ""}
