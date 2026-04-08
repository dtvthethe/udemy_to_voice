#!/usr/bin/env python3

import asyncio
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
import webvtt
import edge_tts
from deep_translator import GoogleTranslator
from pydub import AudioSegment


# ─── Config ───────────────────────────────────────────────────────────────────

# Chọn giọng đọc
VOICES = {
    "nu_nam":  "vi-VN-HoaiMyNeural",   # Giọng nữ miền Nam (mặc định)
    "nam_bac": "vi-VN-NamMinhNeural",  # Giọng nam miền Bắc
}
DEFAULT_VOICE = VOICES["nu_nam"]

# Tốc độ đọc tối đa khi speedup (tránh quá nhanh)
MAX_SPEEDUP = 1.8

# Volume của audio thuyết minh (dB so với gốc)
DUBBING_VOLUME_DB = 0.0

# Volume của audio gốc (giảm xuống để nghe thuyết minh rõ hơn)
ORIGINAL_VOLUME_DB = -20.0  # -20dB = gần tắt tiếng gốc, chỉnh lại nếu muốn


# ─── Data ─────────────────────────────────────────────────────────────────────

@dataclass
class Segment:
    index: int
    start_ms: float   # milliseconds
    end_ms: float
    original_text: str
    translated_text: str = ""
    audio_path: str = ""


# ─── Step 1: Convert .m3u8 → .mp4 ────────────────────────────────────────────

def convert_m3u8_to_mp4(input_path: str, output_path: str):
    """Dùng ffmpeg convert HLS stream sang mp4"""
    print(f"🎬 Converting {input_path} → {output_path} ...")
    cmd = [
        "ffmpeg", "-y",
        "-allowed_extensions", "ALL",
        "-protocol_whitelist", "file,crypto,data,http,https,tcp,tls",
        "-i", input_path,
        "-c", "copy",         # Không re-encode, copy stream
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffmpeg lỗi:\n{result.stderr}")
        sys.exit(1)
    print("✅ Convert video xong!\n")


# ─── Step 2: Parse .vtt ───────────────────────────────────────────────────────

def parse_vtt(vtt_path: str) -> list[Segment]:
    """Parse file .vtt ra list Segment"""
    print(f"📄 Parsing {vtt_path} ...")
    segments = []
    for i, caption in enumerate(webvtt.read(vtt_path)):
        text = caption.text.strip()
        # Bỏ HTML tags nếu có (<i>, <b>, ...)
        text = re.sub(r"<[^>]+>", "", text)
        # Bỏ dòng trống
        text = " ".join(text.split())
        if not text:
            continue
        segments.append(Segment(
            index=i,
            start_ms=caption.start_in_seconds * 1000,
            end_ms=caption.end_in_seconds * 1000,
            original_text=text,
        ))
    print(f"✅ Parsed {len(segments)} segments!\n")
    return segments


# ─── Step 3: Translate ────────────────────────────────────────────────────────

def translate_segments(segments: list[Segment], source_lang: str = "auto") -> list[Segment]:
    """Dịch tất cả segments sang tiếng Việt"""
    print(f"🌐 Đang dịch {len(segments)} segments sang tiếng Việt...")
    translator = GoogleTranslator(source=source_lang, target="vi")

    BATCH = 10
    for i in range(0, len(segments), BATCH):
        batch = segments[i:i + BATCH]
        texts = [s.original_text for s in batch]
        try:
            translated = translator.translate_batch(texts)
            for seg, trans in zip(batch, translated):
                seg.translated_text = trans or seg.original_text
        except Exception as e:
            print(f"  ⚠️ Lỗi dịch batch {i//BATCH}: {e} → Giữ text gốc")
            for seg in batch:
                seg.translated_text = seg.original_text

        progress = min(i + BATCH, len(segments))
        print(f"  → {progress}/{len(segments)} segments", end="\r")

    print(f"\n✅ Dịch xong!\n")
    return segments


# ─── Step 4: TTS từng segment ────────────────────────────────────────────────

async def tts_segment(seg: Segment, output_dir: str, voice: str):
    """Generate TTS audio cho 1 segment"""
    output_path = os.path.join(output_dir, f"seg_{seg.index:05d}.mp3")
    seg.audio_path = output_path

    if os.path.exists(output_path):
        return  # Skip nếu đã có

    try:
        communicate = edge_tts.Communicate(seg.translated_text, voice)
        await communicate.save(output_path)
    except Exception as e:
        print(f"  ⚠️ TTS lỗi segment {seg.index}: {e}")
        # Tạo file audio trống để không bị break
        silence = AudioSegment.silent(duration=100)
        silence.export(output_path, format="mp3")


async def tts_all_segments(segments: list[Segment], output_dir: str, voice: str):
    """Generate TTS song song cho tất cả segments"""
    print(f"🎤 Đang generate TTS cho {len(segments)} segments (voice: {voice})...")
    os.makedirs(output_dir, exist_ok=True)

    # Chạy song song, nhóm 5 để tránh rate limit edge-tts
    CONCURRENT = 5
    for i in range(0, len(segments), CONCURRENT):
        batch = segments[i:i + CONCURRENT]
        tasks = [tts_segment(seg, output_dir, voice) for seg in batch]
        await asyncio.gather(*tasks)
        progress = min(i + CONCURRENT, len(segments))
        print(f"  → {progress}/{len(segments)} segments", end="\r")

    print(f"\n✅ TTS xong!\n")


# ─── Speedup helper (pitch-preserving, ffmpeg atempo) ────────────────────────

def speedup_audio_ffmpeg(input_path: str, output_path: str, ratio: float):
    """Time-stretch audio bằng ffmpeg atempo (giữ nguyên pitch).
    atempo hỗ trợ 0.5~2.0, cần chain nếu ratio > 2.0.
    """
    filters = []
    r = ratio
    while r > 2.0:
        filters.append("atempo=2.0")
        r /= 2.0
    if r > 1.0:
        filters.append(f"atempo={r:.4f}")
    if not filters:
        shutil.copy(input_path, output_path)
        return
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter:a", ",".join(filters),
        "-vn", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        shutil.copy(input_path, output_path)  # fallback: dùng file gốc


# ─── Step 5: Build full audio track ──────────────────────────────────────────

def build_dubbed_audio(segments: list[Segment], video_duration_ms: float, temp_dir: str) -> AudioSegment:
    """
    Ghép tất cả TTS audio vào đúng timestamp,
    speedup nếu audio dài hơn slot
    """
    print(f"🎧 Đang build audio track ({video_duration_ms/1000:.1f}s)...")
    full_audio = AudioSegment.silent(duration=int(video_duration_ms))
    stretched_dir = os.path.join(temp_dir, "tts_stretched")
    os.makedirs(stretched_dir, exist_ok=True)

    for seg in segments:
        if not seg.audio_path or not os.path.exists(seg.audio_path):
            continue

        slot_ms = seg.end_ms - seg.start_ms
        if slot_ms <= 0:
            continue

        try:
            audio = AudioSegment.from_mp3(seg.audio_path)
            audio_ms = len(audio)

            # Speedup nếu audio dài hơn slot (pitch-preserving)
            if audio_ms > slot_ms:
                ratio = min(audio_ms / slot_ms, MAX_SPEEDUP)
                stretched_path = os.path.join(stretched_dir, f"seg_{seg.index:05d}_s.mp3")
                speedup_audio_ffmpeg(seg.audio_path, stretched_path, ratio)
                audio = AudioSegment.from_mp3(stretched_path)

            # Điều chỉnh volume (bỏ qua nếu = 0 để tránh re-process)
            if DUBBING_VOLUME_DB != 0.0:
                audio = audio + DUBBING_VOLUME_DB

            full_audio = full_audio.overlay(audio, position=int(seg.start_ms))

        except Exception as e:
            print(f"  ⚠️ Lỗi segment {seg.index}: {e}")
            continue

    print("✅ Build audio xong!\n")
    return full_audio


# ─── Step 6: Get video duration ──────────────────────────────────────────────

def get_video_duration_ms(video_path: str) -> float | None:
    """Dùng ffprobe để lấy duration của video"""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", 0)) * 1000
    return duration if duration > 0 else None


# ─── Step 6.5: Xuất SRT từ segments ─────────────────────────────────────────

def _ms_to_srt_time(ms: float) -> str:
    h = int(ms // 3_600_000)
    ms %= 3_600_000
    m = int(ms // 60_000)
    ms %= 60_000
    s = int(ms // 1_000)
    millis = int(ms % 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def write_srt_from_segments(segments: list[Segment], path: str):
    """Xuất file .srt từ translated_text của các segment."""
    with open(path, "w", encoding="utf-8") as f:
        idx = 1
        for seg in segments:
            text = seg.translated_text.strip()
            if not text:
                continue
            f.write(f"{idx}\n")
            f.write(f"{_ms_to_srt_time(seg.start_ms)} --> {_ms_to_srt_time(seg.end_ms)}\n")
            f.write(f"{text}\n\n")
            idx += 1
    print(f"  📝 Saved subtitle: {path}\n")


# ─── Step 7: Merge video + dubbed audio ──────────────────────────────────────

def merge_video_audio(video_path: str, dubbed_audio_path: str, output_path: str,
                      keep_original_audio: bool = True,
                      subtitle_path: str | None = None,
                      burn_subtitle: bool = False):
    """Merge video với dubbed audio dùng ffmpeg"""
    print(f"🎞️ Đang merge video + audio → {output_path}...")

    audio_filter = (
        f"[0:a]volume={ORIGINAL_VOLUME_DB}dB[orig];"
        f"[1:a]volume={DUBBING_VOLUME_DB}dB[dub];"
        f"[orig][dub]amix=inputs=2:duration=first[aout]"
    )

    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", dubbed_audio_path]

    if subtitle_path:
        if not burn_subtitle:
            cmd += ["-i", subtitle_path]

    if keep_original_audio:
        cmd += ["-filter_complex", audio_filter]
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "1:a"]

    if burn_subtitle and subtitle_path:
        # Burn-in: cần re-encode video, dùng libx264
        srt_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")
        cmd += [
            "-vf", f"subtitles='{srt_escaped}'",
            "-map", "0:v",
            *audio_map,
            "-c:v", "libx264", "-crf", "18", "-preset", "fast",
            "-c:a", "aac",
            "-shortest", output_path,
        ]
    elif subtitle_path:
        # Soft subtitle: embed track, không re-encode video
        cmd += [
            "-map", "0:v",
            *audio_map,
            "-map", "2:s",
            "-c:v", "copy",
            "-c:a", "aac",
            "-c:s", "mov_text",
            "-shortest", output_path,
        ]
    else:
        cmd += [
            "-map", "0:v",
            *audio_map,
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest", output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ ffmpeg merge lỗi:\n{result.stderr}")
        sys.exit(1)
    print(f"✅ Merge xong! Output: {output_path}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🎬 VTT Dubber - Thuyết minh tiếng Việt cho video"
    )
    parser.add_argument("--video",    required=True, help="Input video (.m3u8 hoặc .mp4)")
    parser.add_argument("--subtitle", required=True, help="Input subtitle (.vtt)")
    parser.add_argument("--output",   default="output_dubbed.mp4", help="Output video (.mp4)")
    parser.add_argument("--voice",    default="nu_nam",
                        choices=list(VOICES.keys()),
                        help="Chọn giọng đọc: nu_nam (mặc định), nam_bac")
    parser.add_argument("--lang",     default="auto",
                        help="Ngôn ngữ gốc của subtitle (en/ja/ko/auto)")
    parser.add_argument("--skip-translate", action="store_true",
                        help="Bỏ qua bước dịch (dùng khi subtitle đã là tiếng Việt)")
    parser.add_argument("--no-original-audio", action="store_true",
                        help="Tắt hoàn toàn audio gốc (mặc định: giảm volume)")
    parser.add_argument("--add-subtitle", action="store_true",
                        help="Nhúng subtitle tiếng Việt vào video (soft track, bật/tắt được trong player)")
    parser.add_argument("--burn-subtitle", action="store_true",
                        help="Đốt subtitle vào video (hiển thị luôn, cần re-encode chậm hơn)")
    parser.add_argument("--temp-dir", default="./dubber_temp",
                        help="Thư mục temp để lưu file trung gian")
    args = parser.parse_args()

    voice = VOICES[args.voice]
    temp_dir = args.temp_dir

    # ── Dọn dẹp file từ lần chạy trước ───────────────
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"🗑️  Đã xóa thư mục temp cũ: {temp_dir}")
    if os.path.exists(args.output):
        os.remove(args.output)
        print(f"🗑️  Đã xóa output cũ: {args.output}")

    os.makedirs(temp_dir, exist_ok=True)

    print("=" * 55)
    print("  🐰 VTT Dubber - Thuyết minh tiếng Việt")
    print("=" * 55)
    print(f"  Video   : {args.video}")
    print(f"  Subtitle: {args.subtitle}")
    print(f"  Output  : {args.output}")
    print(f"  Voice   : {voice}")
    print("=" * 55 + "\n")

    # ── Step 1: Convert m3u8 nếu cần ──────────────────
    video_path = args.video
    if video_path.endswith(".m3u8"):
        mp4_path = os.path.join(temp_dir, "video.mp4")
        convert_m3u8_to_mp4(video_path, mp4_path)
        video_path = mp4_path

    # ── Step 2: Parse VTT ─────────────────────────────
    segments = parse_vtt(args.subtitle)
    if not segments:
        print("❌ Không parse được segment nào từ file VTT!")
        sys.exit(1)

    # ── Step 3: Translate ─────────────────────────────
    if args.skip_translate:
        print("⏭️  Bỏ qua bước dịch (subtitle đã là tiếng Việt)\n")
        for seg in segments:
            seg.translated_text = seg.original_text
    else:
        segments = translate_segments(segments, source_lang=args.lang)

    # ── Step 4: TTS ───────────────────────────────────
    tts_dir = os.path.join(temp_dir, "tts_segments")
    asyncio.run(tts_all_segments(segments, tts_dir, voice))

    # ── Step 5: Get video duration ────────────────────
    duration_ms = get_video_duration_ms(video_path)
    if not duration_ms:
        # Fallback: dùng end time của segment cuối + buffer
        duration_ms = segments[-1].end_ms + 3000
        print(f"  ⚠️ Không đọc được duration, dùng fallback: {duration_ms/1000:.1f}s")

    # ── Step 6: Build dubbed audio ────────────────────
    dubbed_audio = build_dubbed_audio(segments, duration_ms, temp_dir)
    dubbed_audio_path = os.path.join(temp_dir, "dubbed_audio.wav")
    dubbed_audio.export(dubbed_audio_path, format="wav")
    print(f"  💾 Saved dubbed audio: {dubbed_audio_path}\n")

    # ── Step 6.5: Xuất SRT nếu cần ──────────────────
    srt_path = None
    if args.add_subtitle or args.burn_subtitle:
        srt_path = os.path.join(temp_dir, "subtitles_vi.srt")
        write_srt_from_segments(segments, srt_path)

    # ── Step 7: Merge ──────────────────────────────────
    merge_video_audio(
        video_path=video_path,
        dubbed_audio_path=dubbed_audio_path,
        output_path=args.output,
        keep_original_audio=not args.no_original_audio,
        subtitle_path=srt_path,
        burn_subtitle=args.burn_subtitle,
    )

    print("=" * 55)
    print(f"  🎉 XONG! File output: {args.output}")
    print("=" * 55)


if __name__ == "__main__":
    main()
