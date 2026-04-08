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
├── main.py              # Chạy từ file input.json (Udemy)
├── main_from_file.py    # Chạy từ file video + subtitle thủ công
├── input.json           # File JSON tải về từ Udemy
├── storage/
│   ├── subtitles/       # File subtitle .vtt tải về tự động
│   └── output/          # File output sau khi xử lý
└── dubber_temp/         # Thư mục tạm (tự tạo & xóa mỗi lần chạy)
```

---

## Get source (input.json)

1. Mở video Udemy trên trình duyệt, nhấn F12 → tab **Network**
2. Tìm request có tên `lectures/<id>/?fields[asset]=...`
3. Copy response body → lưu thành `input.json` ở thư mục gốc dự án

Cấu trúc cần thiết trong `input.json`:
```json
{
  "id": 12345,
  "captions": [
    { "locale_id": "vi_VN", "url": "https://..." },
    { "locale_id": "en_US", "url": "https://..." }
  ],
  "media_sources": [
    { "src": "https://.../video.m3u8" }
  ]
}
```

> Subtitle ưu tiên lấy `vi_VN`. Nếu không có sẽ fallback `en_US` và tự động dịch sang tiếng Việt.

---

## Cách chạy

### Dùng `main.py` — từ file input.json (khuyến nghị)

```bash
# Cơ bản
python main.py --output storage/output/video_tiengviet.mp4

# Có nhúng subtitle + chọn giọng nu_nam
python main.py --output storage/output/video_tiengviet.mp4 --voice nu_nam --add-subtitle

# Đốt subtitle vào video (hiển thị luôn)
python main.py --output storage/output/video_tiengviet.mp4 --burn-subtitle

# Dùng file json khác
python main.py --input other_video.json --output storage/output/video2.mp4
```

### Dùng `main_from_file.py` — từ file video + subtitle thủ công

```bash
python main_from_file.py \
  --video storage/videos/1.m3u8 \
  --subtitle storage/subtitles/1.vtt \
  --output storage/output/video_tiengviet.mp4 \
  --skip-translate --add-subtitle
```

### trường hợp ko thể download file m3u8

- record lại dưới dạng file .mp4
- download thủ công file subtitle

```bash
python main_from_file.py \
  --video storage/videos/1.mp4 \
  --subtitle storage/subtitles/1.vtt \
  --output storage/output/video_tiengviet.mp4 \
  --skip-translate --add-subtitle
```



---

## Options — main.py

| Option | Mặc định | Mô tả |
|---|---|---|
| `--input` | `input.json` | File JSON input tải về từ Udemy |
| `--output` | `output_dubbed.mp4` | Tên file video đầu ra |
| `--voice` | `nu_nam` | Giọng đọc: `nu_nam` (nữ Nam) hoặc `nam_bac` (nam Bắc) |
| `--no-original-audio` | `false` | Tắt hoàn toàn tiếng gốc (mặc định: giảm xuống -20dB) |
| `--add-subtitle` | `false` | Nhúng subtitle vào video (soft track, bật/tắt được trong player) |
| `--burn-subtitle` | `false` | Đốt subtitle vào video (hiển thị luôn, cần re-encode) |
| `--temp-dir` | `./dubber_temp` | Thư mục lưu file trung gian |

## Options — main_from_file.py

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
