import pytest
from app.youtube import extract_video_id


@pytest.mark.parametrize("value", [
    "yTwvX2RJ80Q",
    "https://www.youtube.com/watch?v=yTwvX2RJ80Q",
    "https://youtu.be/yTwvX2RJ80Q",
    "https://www.youtube.com/shorts/yTwvX2RJ80Q",
    "https://www.youtube.com/embed/yTwvX2RJ80Q",
])
def test_extract_video_id(value):
    assert extract_video_id(value) == "yTwvX2RJ80Q"


def test_invalid_url():
    with pytest.raises(ValueError):
        extract_video_id("https://example.com/not-youtube")
