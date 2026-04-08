## bối cảnh
flow dự án hiện tại sẽ đọc 2 file input là video và subtitle từ file mình download về để tạo video

## Mô tả task
mình muốn dựa vào `file main_form_file.py` hãy phát triển file `main.py` theo cách là:
    - mình sẽ download file input `.json` từ udemy về và để tại đường dẫn thư mục gốc dự án `input.json`
    - cấu trúc file `input.json`:

    ```json
        {
            ...
            "captions": [
                {
                    ...
                    "url": "url của file subtitle .vtt tiếng Nhật",
                    "locale_id": "jp_JP",
                },
                {
                    ...
                    "url": "url của file subtitle .vtt tiếng Việt",
                    "locale_id": "vi_VN",
                },
                ...
            ],
            ....
            "media_sources": [
                {
                    "src": "url của file video .m3u8",
                    ...
                }
            ]
        }
    ```

    - thực hiện đọc file json để lấy 2 giá trị sau:
        + đường dẫn video là: `media_sources[0].src`
        + đường dẫn file subtitle: `captions[lấy object dựa vào locale_id = "vn_VN"].url`
    - thực hiện download video và subtitle vào thư mục như sau:
        + video: `storage/videos/tên file video riêng biệt không bị nhầm với video khác là được`
        + subtitle: `storage/subtitles/tên file subtitle riêng biệt không bị nhầm với subtitle khác là được`
    - từ 2 files đã download trên hãy tạo video theo logic như file `main_from_file.py`
    - ở câu lệnh chạy để tạo video hãy cho user thêm 1 flag để  nhập vào tên output video
    - update lại file readme.md

