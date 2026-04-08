#!/usr/bin/env python3

import asyncio
import argparse
import json
import os
import shutil
import sys
import urllib.request

from main_from_file import (
    VOICES,
    convert_m3u8_to_mp4,
    parse_vtt,
    translate_segments,
    tts_all_segments,
    build_dubbed_audio,
    get_video_duration_ms,
    write_srt_from_segments,
    merge_video_audio,
)


# ─── Đọc input.json ───────────────────────────────────────────────────────────

def load_input_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_subtitle_info(data: dict) -> tuple[str, str, bool]:
    """Trả về (url, locale_id, needs_translation).
    Ưu tiên vi_VN, fallback en_US (kèm cảnh báo + bật dịch tự động).
    """
    captions = data.get("captions", [])

    vi_caption = next((c for c in captions if c.get("locale_id") == "vi_VN"), None)
    if vi_caption:
        return vi_caption["url"], "vi_VN", False

    print("⚠️  Không tìm thấy subtitle tiếng Việt (vi_VN).")
    print("    → Dùng subtitle tiếng Anh (en_US) và sẽ tự động dịch sang tiếng Việt.\n")
    en_caption = next((c for c in captions if c.get("locale_id") == "en_US"), None)
    if en_caption:
        return en_caption["url"], "en_US", True

    print("❌ Không tìm thấy subtitle vi_VN hoặc en_US trong file JSON!")
    sys.exit(1)


def get_video_url(data: dict) -> str:
    sources = data.get("media_sources", [])
    m3u8 = next((s for s in sources if s.get("type") == "application/x-mpegURL"), None)
    if not m3u8:
        print("❌ Không tìm thấy media source application/x-mpegURL trong file JSON!")
        sys.exit(1)
    return m3u8["src"]


# ─── Download subtitle ────────────────────────────────────────────────────────

def download_subtitle(url: str, locale_id: str, asset_id: int, output_dir: str) -> str:
    """Download file .vtt subtitle về storage/subtitles/"""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{asset_id}_{locale_id}.vtt"
    path = os.path.join(output_dir, filename)

    if os.path.exists(path):
        print(f"  📄 Subtitle đã tồn tại, dùng lại: {path}\n")
        return path

    print(f"📥 Đang download subtitle ({locale_id}) → {path} ...")
    urllib.request.urlretrieve(url, path)
    print(f"  ✅ Download subtitle xong!\n")
    return path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🎬 VTT Dubber - Thuyết minh tiếng Việt từ file input.json Udemy"
    )
    parser.add_argument("--input",   default="input.json",
                        help="File JSON input từ Udemy (default: input.json)")
    parser.add_argument("--output",  default="output_dubbed.mp4",
                        help="Tên file output video (.mp4, default: output_dubbed.mp4)")
    parser.add_argument("--voice",   default="nu_nam",
                        choices=list(VOICES.keys()),
                        help="Chọn giọng đọc: nu_nam (mặc định), nam_bac")
    parser.add_argument("--no-original-audio", action="store_true",
                        help="Tắt hoàn toàn audio gốc (mặc định: giảm volume)")
    parser.add_argument("--add-subtitle", action="store_true",
                        help="Nhúng subtitle tiếng Việt vào video (soft track, bật/tắt được trong player)")
    parser.add_argument("--burn-subtitle", action="store_true",
                        help="Đốt subtitle vào video (hiển thị luôn, cần re-encode chậm hơn)")
    parser.add_argument("--temp-dir", default="./dubber_temp",
                        help="Thư mục temp để lưu file trung gian (default: ./dubber_temp)")
    args = parser.parse_args()

    voice = VOICES[args.voice]
    temp_dir = args.temp_dir

    # ── Dọn dẹp từ lần chạy trước ────────────────────
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"🗑️  Đã xóa thư mục temp cũ: {temp_dir}")
    if os.path.exists(args.output):
        os.remove(args.output)
        print(f"🗑️  Đã xóa output cũ: {args.output}")

    os.makedirs(temp_dir, exist_ok=True)

    # ── Đọc input.json ────────────────────────────────
    print(f"📂 Đọc file: {args.input}")
    data = load_input_json(args.input)
    asset_id = data.get("id", "unknown")

    video_url = get_video_url(data)
    subtitle_url, locale_id, needs_translation = get_subtitle_info(data)

    print("=" * 55)
    print("  🐰 VTT Dubber - Thuyết minh tiếng Việt")
    print("=" * 55)
    print(f"  Asset ID : {asset_id}")
    print(f"  Subtitle : {locale_id}")
    print(f"  Output   : {args.output}")
    print(f"  Voice    : {voice}")
    print("=" * 55 + "\n")

    # ── Download subtitle ─────────────────────────────
    subtitle_path = download_subtitle(
        subtitle_url, locale_id, asset_id,
        output_dir="storage/subtitles",
    )

    # ── Convert m3u8 → mp4 (stream trực tiếp từ URL) ─
    mp4_path = os.path.join(temp_dir, "video.mp4")
    convert_m3u8_to_mp4(video_url, mp4_path)
    video_path = mp4_path

    # ── Parse VTT ─────────────────────────────────────
    segments = parse_vtt(subtitle_path)
    if not segments:
        print("❌ Không parse được segment nào từ file VTT!")
        sys.exit(1)

    # ── Translate nếu cần ─────────────────────────────
    if needs_translation:
        segments = translate_segments(segments, source_lang="en")
    else:
        print("⏭️  Subtitle là tiếng Việt, bỏ qua bước dịch.\n")
        for seg in segments:
            seg.translated_text = seg.original_text

    # ── TTS ───────────────────────────────────────────
    tts_dir = os.path.join(temp_dir, "tts_segments")
    asyncio.run(tts_all_segments(segments, tts_dir, voice))

    # ── Get video duration ────────────────────────────
    duration_ms = get_video_duration_ms(video_path)
    if not duration_ms:
        duration_ms = segments[-1].end_ms + 3000
        print(f"  ⚠️ Không đọc được duration, dùng fallback: {duration_ms/1000:.1f}s")

    # ── Build dubbed audio ────────────────────────────
    dubbed_audio = build_dubbed_audio(segments, duration_ms, temp_dir)
    dubbed_audio_path = os.path.join(temp_dir, "dubbed_audio.wav")
    dubbed_audio.export(dubbed_audio_path, format="wav")
    print(f"  💾 Saved dubbed audio: {dubbed_audio_path}\n")

    # ── Xuất SRT nếu cần ─────────────────────────────
    srt_path = None
    if args.add_subtitle or args.burn_subtitle:
        srt_path = os.path.join(temp_dir, "subtitles_vi.srt")
        write_srt_from_segments(segments, srt_path)

    # ── Merge video + dubbed audio ────────────────────
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
