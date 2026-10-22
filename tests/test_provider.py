from app.youtube import YouTubeTranscriptProvider


class Snip:
    def __init__(self, text, start, duration):
        self.text, self.start, self.duration = text, start, duration


class Track:
    language = "Vietnamese"
    language_code = "vi"
    is_generated = False
    is_translatable = True

    def fetch(self):
        return [Snip(" Xin   chào ", 0, 1.2), Snip(" ", 1.2, 0.2), Snip("thế giới", 1.4, 1)]


class Tracks:
    def find_transcript(self, languages):
        assert languages == ["vi", "en"]
        return Track()

    def __iter__(self):
        return iter([Track()])


class API:
    def list(self, video_id):
        assert video_id == "yTwvX2RJ80Q"
        return Tracks()


class Provider(YouTubeTranscriptProvider):
    def _api(self):
        return API()


def test_fetch_normalizes_and_preserves_timestamps():
    result = Provider().fetch("yTwvX2RJ80Q", ["vi", "en"])
    assert result.text == "Xin chào thế giới"
    assert len(result.segments) == 2
    assert result.segments[0].start == 0
    assert result.segments[0].duration == 1.2
    assert result.language_code == "vi"
    assert result.is_generated is False


def test_list_languages():
    assert Provider().list_languages("yTwvX2RJ80Q")[0].language_code == "vi"


class RequestBlocked(Exception):
    pass


class BlockedAPI:
    def list(self, _):
        raise RequestBlocked("blocked")


class BlockedProvider(YouTubeTranscriptProvider):
    def _api(self):
        return BlockedAPI()


def test_blocked_is_not_no_transcript():
    with __import__("pytest").raises(Exception) as caught:
        BlockedProvider().fetch("yTwvX2RJ80Q", ["vi"])
    assert caught.value.code == "YOUTUBE_REQUEST_BLOCKED"
    assert caught.value.status_code == 503
