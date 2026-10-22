from pydantic import BaseModel, Field, model_validator


class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float


class TranscriptResult(BaseModel):
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool
    segments: list[TranscriptSegment]
    text: str


class LanguageTrack(BaseModel):
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool


class TranscriptRequest(BaseModel):
    url: str | None = None
    video_id: str | None = None
    languages: list[str] = Field(default_factory=lambda: ["vi", "en"])

    @model_validator(mode="after")
    def validate_source(self):
        if bool(self.url) == bool(self.video_id):
            raise ValueError("Provide exactly one of url or video_id")
        return self
