# Project Instructions
## Overview
Đây là một dự án Python để chuyển subtitle .vtt sang thuyết minh tiếng Việt và ghép vào video.
danh sách các từ viết tắt:
- "ntn": "như thế này",
- "ntn?": "như thế nào?",
- "vs": "với",
- "dc": "được",
- "đc": "được",
- "ko": "không",
- "ms": "mới",
- "GGS": "Google Sheets",
- "ENG": "English",
- "JP": "Japan",
- "VN": "Việt Nam",
- "bt": "bài tập"

## Project Structure
- storage/subtitles/: Thư mục chứa các file subtitle .vtt
- storage/videos/: Thư mục chứa các file video gốc .m3u8
- storage/output/: Thư mục chứa các file output video đã được ghép thuyết minh
- main.py: File chính để chạy dự án, chứa logic chuyển subtitle và ghép video

## Tech Stack
python 3.14

## Chạy Dự Án
- lệnh chạy cơn bản:
```
python main.py --video storage/videos/1.m3u8 --subtitle storage/subtitles/1.vtt --skip-translate --add-subtitle
```

- lệnh chạy đầy đủ options
```
python main.py \
  --video storage/videos/1.m3u8 \
  --subtitle storage/subtitles/1.vtt \
  --skip-translate         # nếu đã có subtitle tiếng Việt rồi thì bỏ qua bước dịch
  --add-subtitle # nếu muốn thêm subtitle tiếng Việt vào video, nếu không có option này thì sẽ chỉ ghép thuyết minh mà không có subtitle
  --output storage/output/video_tiengviet.mp4 \
  --voice nu_nam \        # hoặc nam_bac
  --lang en \             # en / ja / ko / auto
  --no-original-audio     # tắt hẳn tiếng gốc
```

## Flow Dự Án
1. Đọc file subtitle .vtt từ thư mục storage/subtitles/
2. Đọc file video gốc .m3u8 từ thư mục storage/videos/
3. Nếu không có option --skip-translate thì dịch subtitle sang tiếng Việt
4. Tạo file thuyết minh TTS từ subtitle tiếng Việt
5. Ghép thuyết minh vào video gốc, nếu có option --add-subtitle thì sẽ thêm subtitle tiếng Việt vào video, nếu không có thì chỉ ghép thuyết minh mà không có subtitle
6. Xuất file video đã được ghép thuyết minh

