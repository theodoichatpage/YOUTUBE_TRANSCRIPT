# YOUTUBE_TRANSCRIPT

Dịch vụ FastAPI độc lập lấy transcript/phụ đề YouTube cho VIDEO IMAGE STUDIO, dùng `youtube-transcript-api`.

## Chạy trên Windows/local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/docs` để xem OpenAPI.

## API

Health:

```bash
curl http://127.0.0.1:8000/health
```

Lấy transcript, ưu tiên tiếng Việt rồi tiếng Anh:

```bash
curl -X POST http://127.0.0.1:8000/transcript -H "Content-Type: application/json" -d "{\"url\":\"https://www.youtube.com/watch?v=yTwvX2RJ80Q\",\"languages\":[\"vi\",\"en\"]}"
```

Danh sách ngôn ngữ:

```bash
curl http://127.0.0.1:8000/transcript/yTwvX2RJ80Q/languages
```

Kết quả transcript chứa `video_id`, ngôn ngữ, trạng thái phụ đề tự động, `segments` (`text`, `start`, `duration`) và `text` đã ghép.

## Docker

```bash
docker build -t youtube-transcript .
docker run --rm -p 8000:8000 youtube-transcript
```

## Lỗi YouTube/IP

`YOUTUBE_IP_BLOCKED` và `YOUTUBE_REQUEST_BLOCKED` nghĩa là YouTube chặn IP/mạng đang chạy service; chúng không có nghĩa video không có phụ đề. Chạy service trên máy local giúp tránh việc yêu cầu đi từ IP Vercel/cloud. Nếu IP local cũng bị chặn, kiến trúc provider cho phép bổ sung proxy hoặc speech-to-text về sau mà không đổi API công khai.

## Test

```bash
pytest -v
```

Sau khi test tự động đạt, dùng video `yTwvX2RJ80Q` với lệnh `/transcript` phía trên để smoke-test thật trên máy sẽ chạy service.
