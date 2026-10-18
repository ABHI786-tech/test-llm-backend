from core.exceptions import (
    DuplicateEmailError,
    DuplicatePersonnelEmailError,
    MediaOutletNotFoundError,
    PersonnelNotFoundError,
)
from models.models import Media_outlets, Personnel, Students
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


# --------------------------------------------------------------------------- #
# Students (existing)
# --------------------------------------------------------------------------- #
async def register_student_repo(std, db):
    student = Students(
        name=std.name,
        age=std.age,
        email=std.email,
    )
    db.add(student)

    try:
        await db.commit()
    except IntegrityError as exc:
        # The failed INSERT leaves the session in a broken state; roll back
        # before translating so the connection can be reused.
        await db.rollback()
        raise DuplicateEmailError(f"Email '{std.email}' is already registered") from exc

    await db.refresh(student)

    return {
        "message": "Student registered successfully",
        "student": {
            "id": student.id,
            "name": student.name,
            "age": student.age,
            "email": student.email,
        },
    }


# --------------------------------------------------------------------------- #
# IntegrityError helpers
# --------------------------------------------------------------------------- #
# Name of the UNIQUE constraint on personnel.email, declared in models/models.py.
PERSONNEL_EMAIL_CONSTRAINT = "uq_personnel_email"

# Postgres SQLSTATE for `unique_violation`. personnel has exactly one unique
# constraint, so this is enough to identify a duplicate email even when the
# constraint name is unavailable.
PG_UNIQUE_VIOLATION = "23505"


def _iter_causes(exc: BaseException | None):
    """Walk the exception chain, bounded so a self-referencing chain cannot hang."""
    seen: set[int] = set()
    depth = 0
    while exc is not None and depth < 10 and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__
        depth += 1


def _is_personnel_email_conflict(exc: IntegrityError) -> bool:
    """Only treat an IntegrityError as a duplicate email when the DB says so.

    `exc.orig` is SQLAlchemy's asyncpg adapter wrapper, which does not carry the
    violated constraint name - the native asyncpg error is on the `__cause__`
    chain. Without this check any integrity failure (bad FK, not-null, length)
    would be mislabeled as a duplicate email.
    """
    chain = list(_iter_causes(exc.orig))
    if any(getattr(e, "constraint_name", None) == PERSONNEL_EMAIL_CONSTRAINT for e in chain):
        return True
    return any(getattr(e, "sqlstate", None) == PG_UNIQUE_VIOLATION for e in chain)


# --------------------------------------------------------------------------- #
# Media outlets
# --------------------------------------------------------------------------- #
async def get_media_outlet_repo(outlet_id: int, db: AsyncSession) -> Media_outlets:
    outlet = await db.get(Media_outlets, outlet_id)
    if outlet is None:
        raise MediaOutletNotFoundError(f"No media outlet with id {outlet_id}")
    return outlet


async def list_media_outlet_repo(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Media_outlets]:
    stmt = select(Media_outlets).order_by(Media_outlets.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_media_outlet_repo(payload, db: AsyncSession) -> Media_outlets:
    outlet_data = payload.model_dump(exclude={"personnel"})
    outlet = Media_outlets(**outlet_data)
    db.add(outlet)

    added: list[Personnel] = []
    for person in payload.personnel:
        row = Personnel(**person.model_dump())
        outlet.personnel.append(row)
        added.append(row)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_personnel_email_conflict(exc):
            raise DuplicatePersonnelEmailError("One of the personnel emails is already in use") from exc
        raise

    await db.refresh(outlet)
    return outlet


async def update_media_outlet_repo(
    outlet_id: int, payload, db: AsyncSession
) -> tuple[Media_outlets, list[str], list[int], list[int]]:
    """Partial update of the outlet plus upsert/removal of nested personnel."""
    outlet = await get_media_outlet_repo(outlet_id, db)

    # Only the outlet's own columns; personnel is handled separately below.
    outlet_fields = payload.model_dump(exclude={"personnel", "remove_personnel_ids"}, exclude_unset=True)
    updated_fields: list[str] = list(outlet_fields.keys())
    for field, value in outlet_fields.items():
        setattr(outlet, field, value)

    existing = {p.id: p for p in outlet.personnel}
    added_rows: list[Personnel] = []

    for entry in payload.personnel or []:
        values = entry.model_dump(exclude_unset=True)
        person_id = values.pop("id", None)
        if person_id is not None:
            row = existing.get(person_id)
            if row is None:
                raise PersonnelNotFoundError(f"No personnel with id {person_id} on media outlet {outlet_id}")
            for field, value in values.items():
                setattr(row, field, value)
        else:
            row = Personnel(media_outlet_id=outlet.id, **values)
            outlet.personnel.append(row)
            added_rows.append(row)

    removed_ids: list[int] = []
    for person_id in payload.remove_personnel_ids or []:
        row = existing.get(person_id)
        if row is None:
            raise PersonnelNotFoundError(f"No personnel with id {person_id} on media outlet {outlet_id}")
        outlet.personnel.remove(row)
        removed_ids.append(person_id)

    try:
        # Flush before commit so inserted rows have real ids we can report.
        await db.flush()
        added_ids = [row.id for row in added_rows]
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_personnel_email_conflict(exc):
            raise DuplicatePersonnelEmailError("One of the personnel emails is already in use") from exc
        raise

    await db.refresh(outlet)

    return outlet, updated_fields, added_ids, removed_ids


async def delete_media_outlet_repo(outlet_id: int, db: AsyncSession) -> None:
    outlet = await get_media_outlet_repo(outlet_id, db)
    await db.delete(outlet)
    await db.commit()


# --------------------------------------------------------------------------- #
# Personnel (always scoped to a media outlet)
# --------------------------------------------------------------------------- #
async def list_personnel_repo(outlet_id: int, db: AsyncSession) -> list[Personnel]:
    await get_media_outlet_repo(outlet_id, db)
    stmt = select(Personnel).where(Personnel.media_outlet_id == outlet_id).order_by(Personnel.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_personnel_repo(outlet_id: int, payload, db: AsyncSession) -> Personnel:
    outlet = await get_media_outlet_repo(outlet_id, db)

    person = Personnel(media_outlet_id=outlet.id, **payload.model_dump())
    outlet.personnel.append(person)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_personnel_email_conflict(exc):
            raise DuplicatePersonnelEmailError(f"Email '{payload.email}' is already in use") from exc
        raise

    await db.refresh(person)
    return person


async def get_personnel_repo(outlet_id: int, person_id: int, db: AsyncSession) -> Personnel:
    await get_media_outlet_repo(outlet_id, db)
    stmt = select(Personnel).where(Personnel.id == person_id, Personnel.media_outlet_id == outlet_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise PersonnelNotFoundError(f"No personnel with id {person_id} on media outlet {outlet_id}")
    return row


async def update_personnel_repo(outlet_id: int, person_id: int, payload, db: AsyncSession) -> Personnel:
    person = await get_personnel_repo(outlet_id, person_id, db)

    # `id` is only an upsert marker in the nested list; never write it as a column.
    changes = payload.model_dump(exclude={"id"}, exclude_unset=True)
    for field, value in changes.items():
        setattr(person, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_personnel_email_conflict(exc):
            raise DuplicatePersonnelEmailError(f"Email '{changes.get('email')}' is already in use") from exc
        raise

    await db.refresh(person)
    return person


async def delete_personnel_repo(outlet_id: int, person_id: int, db: AsyncSession) -> None:
    person = await get_personnel_repo(outlet_id, person_id, db)
    await db.delete(person)
    await db.commit()