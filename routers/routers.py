from  core.database import get_db
from  schemas.schemas import (
    CreateMediaOutletResponse,
    MediaOutletAnswerResponse,
    MediaOutletOut,
    MediaOutletSchemas,
    MediaOutletUpdateSchemas,
    PersonnelOut,
    PersonnelSchemas,
    PersonnelUpdateSchemas,
    RegisterStudentResponse,
    StudentSchemas,
    SuggestResponse,
    UpdateMediaOutletResponse,
)
from  services.services import (
    ask_about_media_outlet_service,
    create_media_outlet_service,
    create_personnel_service,
    delete_media_outlet_service,
    delete_personnel_service,
    get_media_outlet_service,
    get_personnel_service,
    list_media_outlet_service,
    list_personnel_service,
    register_student_service,
    suggest_fields_service,
    update_media_outlet_service,
    update_personnel_service,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/register", response_model=RegisterStudentResponse)
async def register_student(
    std: StudentSchemas,
    db: AsyncSession = Depends(get_db),
):
    result = await register_student_service(std, db)
    return result


# --------------------------------------------------------------------------- #
# Media outlets
# --------------------------------------------------------------------------- #
outlet_router = APIRouter(prefix="/media-outlets", tags=["media-outlets"])


@outlet_router.post("", response_model=CreateMediaOutletResponse, status_code=201)
async def create_media_outlet(
    payload: MediaOutletSchemas,
    db: AsyncSession = Depends(get_db),
):
    """Create a media outlet. `payload.personnel` may carry the people already
    attached to it, so the whole aggregate is created in one call."""
    outlet = await create_media_outlet_service(payload, db)
    return {"message": "Media outlet created successfully", "media_outlet": outlet}


@outlet_router.get("", response_model=list[MediaOutletOut])
async def list_media_outlets(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await list_media_outlet_service(db, limit=limit, offset=offset)


@outlet_router.get("/{outlet_id}", response_model=MediaOutletOut)
async def get_media_outlet(
    outlet_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await get_media_outlet_service(outlet_id, db)


@outlet_router.patch("/{outlet_id}", response_model=UpdateMediaOutletResponse)
async def update_media_outlet(
    outlet_id: int,
    payload: MediaOutletUpdateSchemas,
    db: AsyncSession = Depends(get_db),
):
    """Partial update.

    - top-level keys: only what you send is written
    - `personnel`: list of upserts, keyed by `id` (id = update, no id = insert)
    - `remove_personnel_ids`: explicit deletes, so a PATCH never drops people silently
    """
    outlet, updated_fields, added_ids, removed_ids = await update_media_outlet_service(outlet_id, payload, db)
    return {
        "message": "Media outlet updated successfully",
        "updated_fields": updated_fields,
        "added_personnel_ids": added_ids,
        "removed_personnel_ids": removed_ids,
        "media_outlet": outlet,
    }


@outlet_router.delete("/{outlet_id}", status_code=204)
async def delete_media_outlet(
    outlet_id: int,
    db: AsyncSession = Depends(get_db),
):
    await delete_media_outlet_service(outlet_id, db)


@outlet_router.post("/{outlet_id}/ask", response_model=MediaOutletAnswerResponse)
async def ask_about_media_outlet(
    outlet_id: int,
    question: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Natural-language question, e.g. 'what is the email of the editor?'",
        examples=["what is the email of the editor?"],
    ),
    db: AsyncSession = Depends(get_db),
):
    """Fetch the media outlet and its personnel, convert to JSON, and let the LLM
    answer strictly from the record's key fields."""
    record, result = await ask_about_media_outlet_service(outlet_id, question, db)
    return {"question": question, "record": record, "result": result}


@outlet_router.post("/{outlet_id}/suggest", response_model=SuggestResponse)
async def suggest_media_outlet_fields(
    outlet_id: int,
    columns: str = Query(
        "gpt",
        description="Comma-separated model columns to run: claude, gemini, gpt.",
        examples=["claude,gpt"],
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run the chosen models over the record and return per-field suggestions.

    Each column is independent: a model that fails reports its own error in the
    response and the others still come back.
    """
    wanted = [c.strip().lower() for c in columns.split(",") if c.strip()]
    return await suggest_fields_service(outlet_id, wanted, db)


# --------------------------------------------------------------------------- #
# Personnel (nested under a media outlet)
# --------------------------------------------------------------------------- #
personnel_router = APIRouter(prefix="/media-outlets/{outlet_id}/personnel", tags=["personnel"])


@personnel_router.get("", response_model=list[PersonnelOut])
async def list_personnel(
    outlet_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await list_personnel_service(outlet_id, db)


@personnel_router.post("", response_model=PersonnelOut, status_code=201)
async def create_personnel(
    outlet_id: int,
    payload: PersonnelSchemas,
    db: AsyncSession = Depends(get_db),
):
    """Add a person to this media outlet."""
    return await create_personnel_service(outlet_id, payload, db)


@personnel_router.get("/{person_id}", response_model=PersonnelOut)
async def get_personnel(
    outlet_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await get_personnel_service(outlet_id, person_id, db)


@personnel_router.patch("/{person_id}", response_model=PersonnelOut)
async def update_personnel(
    outlet_id: int,
    person_id: int,
    payload: PersonnelUpdateSchemas,
    db: AsyncSession = Depends(get_db),
):
    """Partial update of one person."""
    return await update_personnel_service(outlet_id, person_id, payload, db)


@personnel_router.delete("/{person_id}", status_code=204)
async def delete_personnel(
    outlet_id: int,
    person_id: int,
    db: AsyncSession = Depends(get_db),
):
    await delete_personnel_service(outlet_id, person_id, db)