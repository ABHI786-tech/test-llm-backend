from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# --------------------------------------------------------------------------- #
# Students (existing)
# --------------------------------------------------------------------------- #
class StudentSchemas(BaseModel):
    name: str
    age: int
    email: str


class StudentOut(BaseModel):
    id: int
    name: str
    age: int
    email: str


class RegisterStudentResponse(BaseModel):
    message: str
    student: StudentOut


# --------------------------------------------------------------------------- #
# Personnel (nested under a media outlet)
# --------------------------------------------------------------------------- #
class PersonnelSchemas(BaseModel):
    """Create payload. Mirrors the writable columns of the Personnel model."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=120, examples=["Ada"])
    last_name: str = Field(min_length=1, max_length=120, examples=["Lovelace"])
    email: str = Field(max_length=320, examples=["ada@example.com"])
    phone: str | None = Field(default=None, max_length=32, examples=["+44 20 7946 0000"])
    title: str | None = Field(default=None, max_length=160, examples=["Head of News"])
    linkedin_url: str | None = Field(
        default=None,
        max_length=512,
        examples=["https://www.linkedin.com/in/ada-lovelace"],
    )


class PersonnelUpdateSchemas(BaseModel):
    """Partial update. Only the fields you send are written; the rest are untouched.

    `id` is optional and only meaningful inside a media outlet's `personnel` list, where
    it marks an entry as an update of an existing person rather than an insert.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id: int | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, max_length=160)
    linkedin_url: str | None = Field(default=None, max_length=512)


class PersonnelOut(BaseModel):
    """Full model shape returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    media_outlet_id: int | None
    first_name: str
    last_name: str
    email: str
    phone: str | None
    title: str | None
    linkedin_url: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Media outlets
# --------------------------------------------------------------------------- #
class MediaOutletSchemas(BaseModel):
    """Create a media outlet together with the personnel that belong to it."""

    model_config = ConfigDict(str_strip_whitespace=True)

    maven_id: str = Field(max_length=64, examples=["maven-1042"])
    name: str = Field(max_length=255, examples=["The Daily Chronicle"])
    aliases: list[str] = Field(default_factory=list, examples=[["Chronicle", "Daily Chron"]])
    slogan: str = Field(default="", examples=["All the news that fits"])
    website: str = Field(default="", examples=["https://example.com"])
    email: str = Field(default="", max_length=320, examples=["hello@example.com"])
    phone: str = Field(default="", max_length=32)
    linkedin_url: str = Field(default="", max_length=512)

    media_type: str = Field(default="", max_length=120, examples=["newspaper"])
    subtype: str = Field(default="", max_length=120, examples=["national_daily"])
    categories: str = Field(default="", examples=["news,politics"])
    language: str = Field(default="", max_length=120, examples=["English"])
    geo_appeals: str = Field(default="", examples=["GB,IE"])
    start_date: str = Field(default="", max_length=32, examples=["1855"])

    direct_owner: str = Field(default="", max_length=255, examples=["Chronicle Group"])
    parents: str = Field(default="", examples=["Chronicle Group"])

    diverse_target: str = Field(default="")
    diverse_any: str = Field(default="")
    classified: str = Field(default="", max_length=120)
    certified: str = Field(default="", max_length=120)

    personnel: list[PersonnelSchemas] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_duplicate_emails(self) -> MediaOutletSchemas:
        emails = [p.email.lower() for p in self.personnel]
        if len(emails) != len(set(emails)):
            raise ValueError("personnel contains duplicate email addresses")
        return self


class MediaOutletUpdateSchemas(BaseModel):
    """Partial update.

    Every top-level field is optional and only the ones you send are written.
    `personnel` is a list of upserts keyed by `id`: an entry with an id updates that
    existing person, an entry without one is inserted.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    maven_id: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    aliases: list[str] | None = None
    slogan: str | None = None
    website: str | None = None
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    linkedin_url: str | None = Field(default=None, max_length=512)

    media_type: str | None = Field(default=None, max_length=120)
    subtype: str | None = Field(default=None, max_length=120)
    categories: str | None = None
    language: str | None = Field(default=None, max_length=120)
    geo_appeals: str | None = None
    start_date: str | None = Field(default=None, max_length=32)

    direct_owner: str | None = Field(default=None, max_length=255)
    parents: str | None = None

    diverse_target: str | None = None
    diverse_any: str | None = None
    classified: str | None = Field(default=None, max_length=120)
    certified: str | None = Field(default=None, max_length=120)

    # id is optional: present = update that person, absent = insert a new one.
    personnel: list[PersonnelUpdateSchemas] | None = None

    # Explicit removal, so a PATCH never silently deletes people.
    remove_personnel_ids: list[int] | None = None


class MediaOutletOut(BaseModel):
    """Full model shape, with nested personnel."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    maven_id: str
    name: str
    aliases: list[str]
    slogan: str
    website: str
    email: str
    phone: str
    linkedin_url: str

    media_type: str
    subtype: str
    categories: str
    language: str
    geo_appeals: str
    start_date: str

    direct_owner: str
    parents: str

    diverse_target: str
    diverse_any: str
    classified: str
    certified: str

    personnel: list[PersonnelOut] = Field(default_factory=list)


class CreateMediaOutletResponse(BaseModel):
    message: str
    media_outlet: MediaOutletOut


class UpdateMediaOutletResponse(BaseModel):
    message: str
    updated_fields: list[str]
    added_personnel_ids: list[int]
    removed_personnel_ids: list[int]
    media_outlet: MediaOutletOut


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
class PersonnelRecord(BaseModel):
    """Nested person, as handed to the LLM."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None
    title: str | None
    linkedin_url: str | None


class MediaOutletRecord(BaseModel):
    """The JSON document handed to the LLM as ground truth."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    maven_id: str
    name: str
    aliases: list[str]
    slogan: str
    website: str
    email: str
    phone: str
    linkedin_url: str
    media_type: str
    subtype: str
    categories: str
    language: str
    geo_appeals: str
    start_date: str
    direct_owner: str
    parents: str
    diverse_target: str
    diverse_any: str
    classified: str
    certified: str
    personnel: list[PersonnelRecord] = Field(default_factory=list)


class MediaOutletAnswer(BaseModel):
    """Structured answer the model must fill in from the record it was given."""

    matched_field: str | None = Field(
        default=None,
        description=(
            "The key field the question maps to. Use dotted paths for nested people, "
            "e.g. 'personnel.title'. Null if nothing matched."
        ),
    )
    value: str | None = Field(default=None, description="The value of that key field, verbatim from the record.")
    matched_personnel_id: int | None = Field(
        default=None,
        description="Id of the nested person the answer came from, if the question was about a person.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    answer: str = Field(description="One or two sentences answering using only the record.")
    used_only_record_data: bool = True


class MediaOutletAnswerResponse(BaseModel):
    question: str
    record: MediaOutletRecord
    result: MediaOutletAnswer


# --------------------------------------------------------------------------- #
# Per-field suggestions (the "Run LLM" button in the review grid)
# --------------------------------------------------------------------------- #
class FieldSuggestion(BaseModel):
    """One proposed value for one field of the record."""

    key: str = Field(description="Field key, e.g. 'name' or 'language'.")
    value: str | list[str] | None = Field(
        default=None,
        description="Suggested value; null when the model has nothing to add.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    note: str | None = Field(default=None, max_length=200)


class OutletSuggestions(BaseModel):
    """What one model proposed for the whole record."""

    suggestions: list[FieldSuggestion] = Field(default_factory=list)


class ModelSuggestions(BaseModel):
    """Suggestions from one model column, or the reason it could not run.

    A model that fails does not fail the request: `error` is set and the other
    columns still come back.
    """

    column: str = Field(description="Column id: claude, gemini or gpt.")
    model: str = Field(description="LiteLLM model id that was called.")
    ok: bool = True
    error: str | None = None
    suggestions: list[FieldSuggestion] = Field(default_factory=list)

    def by_key(self) -> dict[str, FieldSuggestion]:
        return {s.key: s for s in self.suggestions}


class SuggestResponse(BaseModel):
    media_outlet_id: int
    record: MediaOutletRecord
    columns: list[ModelSuggestions]