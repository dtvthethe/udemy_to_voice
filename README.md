# Thuyết minh tiếng Việt cho video

Tool Python để đọc subtitle `.vtt`, dịch sang tiếng Việt, tạo giọng đọc TTS rồi ghép vào video gốc.

---

## Yêu cầu hệ thống (Ubuntu)

### 1. ffmpeg (bắt buộc)

```bash
sudo apt install ffmpeg
```

### 3. Thư viện âm thanh (pydub dependency)

```bash
sudo apt install libmp3lame0 libavcodec-extra
```

## Cấu trúc thư mục

```
.
├── main.py
├── storage/
│   ├── videos/        # File video gốc (.m3u8)
│   ├── subtitles/     # File subtitle (.vtt)
│   └── output/        # File output sau khi xử lý
└── dubber_temp/       # Thư mục tạm (tự tạo & xóa mỗi lần chạy)
```

---

## Cách chạy

### Lệnh cơ bản (subtitle đã là tiếng Việt)

```bash
python main.py \
  --video storage/videos/1.m3u8 \
  --subtitle storage/subtitles/1.vtt \
  --skip-translate \
  --add-subtitle
```

### Lệnh đầy đủ options

```bash
python main.py \
  --video storage/videos/1.m3u8 \
  --subtitle storage/subtitles/1.vtt \
  --output storage/output/video_tiengviet.mp4 \
  --voice nu_nam \
  --lang en \
  --skip-translate \
  --add-subtitle
```

---

## Options

| Option | Mặc định | Mô tả |
|---|---|---|
| `--video` | *(bắt buộc)* | File video đầu vào (`.m3u8` hoặc `.mp4`) |
| `--subtitle` | *(bắt buộc)* | File subtitle đầu vào (`.vtt`) |
| `--output` | `output_dubbed.mp4` | File video đầu ra |
| `--voice` | `nu_nam` | Giọng đọc: `nu_nam` (nữ Nam) hoặc `nam_bac` (nam Bắc) |
| `--lang` | `auto` | Ngôn ngữ gốc của subtitle: `en`, `ja`, `ko`, `auto` |
| `--skip-translate` | `false` | Bỏ qua bước dịch (subtitle đã là tiếng Việt) |
| `--no-original-audio` | `false` | Tắt hoàn toàn tiếng gốc (mặc định: giảm xuống -20dB) |
| `--add-subtitle` | `false` | Nhúng subtitle vào video (soft track, bật/tắt được trong player) |
| `--burn-subtitle` | `false` | Đốt subtitle vào video (hiển thị luôn, cần re-encode) |
| `--temp-dir` | `./dubber_temp` | Thư mục lưu file trung gian |
