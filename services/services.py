from  core.exceptions import AppError, LLMNotConfiguredError
from  repo.repo import (
    create_media_outlet_repo,
    create_personnel_repo,
    delete_media_outlet_repo,
    delete_personnel_repo,
    get_media_outlet_repo,
    get_personnel_repo,
    list_media_outlet_repo,
    list_personnel_repo,
    register_student_repo,
    update_media_outlet_repo,
    update_personnel_repo,
)
from  schemas.schemas import (
    MediaOutletAnswer,
    MediaOutletRecord,
    MediaOutletSchemas,
    MediaOutletUpdateSchemas,
    ModelSuggestions,
    PersonnelRecord,
    PersonnelSchemas,
    PersonnelUpdateSchemas,
    SuggestResponse,
)
from  services.llm import MODEL_REGISTRY, answer_about_media_outlet, suggest_fields
from sqlalchemy.ext.asyncio import AsyncSession


async def register_student_service(std, db):
    result = await register_student_repo(std, db)
    return result


# --------------------------------------------------------------------------- #
# Media outlets
# --------------------------------------------------------------------------- #
async def create_media_outlet_service(payload: MediaOutletSchemas, db: AsyncSession):
    return await create_media_outlet_repo(payload, db)


async def get_media_outlet_service(outlet_id: int, db: AsyncSession):
    return await get_media_outlet_repo(outlet_id, db)


async def list_media_outlet_service(db: AsyncSession, limit: int = 50, offset: int = 0):
    return await list_media_outlet_repo(db, limit=limit, offset=offset)


async def update_media_outlet_service(outlet_id: int, payload: MediaOutletUpdateSchemas, db: AsyncSession):
    """Partial update: only the keys present in `payload` are written."""
    return await update_media_outlet_repo(outlet_id, payload, db)


async def delete_media_outlet_service(outlet_id: int, db: AsyncSession) -> None:
    await delete_media_outlet_repo(outlet_id, db)


# --------------------------------------------------------------------------- #
# Personnel (scoped to a media outlet)
# --------------------------------------------------------------------------- #
async def list_personnel_service(outlet_id: int, db: AsyncSession):
    return await list_personnel_repo(outlet_id, db)


async def create_personnel_service(outlet_id: int, payload: PersonnelSchemas, db: AsyncSession):
    return await create_personnel_repo(outlet_id, payload, db)


async def get_personnel_service(outlet_id: int, person_id: int, db: AsyncSession):
    return await get_personnel_repo(outlet_id, person_id, db)


async def update_personnel_service(outlet_id: int, person_id: int, payload: PersonnelUpdateSchemas, db: AsyncSession):
    return await update_personnel_repo(outlet_id, person_id, payload, db)


async def delete_personnel_service(outlet_id: int, person_id: int, db: AsyncSession) -> None:
    await delete_personnel_repo(outlet_id, person_id, db)


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
def _person_to_record(person) -> PersonnelRecord:
    return PersonnelRecord(
        id=person.id,
        first_name=person.first_name,
        last_name=person.last_name,
        email=person.email,
        phone=person.phone,
        title=person.title,
        linkedin_url=person.linkedin_url,
    )


async def _to_record(outlet) -> MediaOutletRecord:
    """Flatten an outlet (with its nested personnel) into the JSON sent to the LLM."""
    return MediaOutletRecord(
        id=outlet.id,
        maven_id=outlet.maven_id,
        name=outlet.name,
        aliases=outlet.aliases,
        slogan=outlet.slogan,
        website=outlet.website,
        email=outlet.email,
        phone=outlet.phone,
        linkedin_url=outlet.linkedin_url,
        media_type=outlet.media_type,
        subtype=outlet.subtype,
        categories=outlet.categories,
        language=outlet.language,
        geo_appeals=outlet.geo_appeals,
        start_date=outlet.start_date,
        direct_owner=outlet.direct_owner,
        parents=outlet.parents,
        diverse_target=outlet.diverse_target,
        diverse_any=outlet.diverse_any,
        classified=outlet.classified,
        certified=outlet.certified,
        personnel=[_person_to_record(p) for p in outlet.personnel],
    )


async def ask_about_media_outlet_service(
    outlet_id: int, question: str, db: AsyncSession
) -> tuple[MediaOutletRecord, MediaOutletAnswer]:
    """Fetch the outlet, convert it to JSON, hand it to the LLM, return both.

    The record is returned alongside the answer so the caller can echo the exact
    JSON document that was the model's only source of truth.
    """
    outlet = await get_media_outlet_repo(outlet_id, db)
    record = await _to_record(outlet)
    answer = await answer_about_media_outlet(record, question)
    return record, answer


# Field keys the model is allowed to suggest on. Matches the grid's sections in
# the frontend (`lib/reviewFields.ts`).
SUGGESTABLE_KEYS = [
    "name",
    "aliases",
    "slogan",
    "website",
    "linkedin_url",
    "phone",
    "email",
    "classified",
    "media_type",
    "subtype",
    "categories",
    "language",
    "geo_appeals",
    "start_date",
    "direct_owner",
    "parents",
    "diverse_target",
    "diverse_any",
    "certified",
]


async def suggest_fields_service(outlet_id: int, columns: list[str], db: AsyncSession) -> SuggestResponse:
    """Run the requested model columns over one record and collect their suggestions.

    Each column runs independently: a model that fails (missing key, provider error)
    reports its own `error` and the remaining columns still return, so one bad key
    does not blank the whole grid.
    """
    outlet = await get_media_outlet_repo(outlet_id, db)
    record = await _to_record(outlet)

    wanted = [c for c in columns if c in MODEL_REGISTRY]
    if not wanted:
        raise LLMNotConfiguredError(f"Unknown model column(s): {', '.join(columns) or 'none given'}")

    results: list[ModelSuggestions] = []
    for column in wanted:
        model = MODEL_REGISTRY[column]
        try:
            suggestions = await suggest_fields(record, SUGGESTABLE_KEYS, model)
            results.append(
                ModelSuggestions(
                    column=column,
                    model=model,
                    ok=True,
                    suggestions=suggestions.suggestions,
                )
            )
        except AppError as exc:
            # Per-column failure: report it, keep going.
            results.append(
                ModelSuggestions(column=column, model=model, ok=False, error=exc.detail, suggestions=[])
            )

    return SuggestResponse(media_outlet_id=outlet_id, record=record, columns=results)