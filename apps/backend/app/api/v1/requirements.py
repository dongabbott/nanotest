"""Requirement management API endpoints."""
import hashlib
import math
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Text, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.domain.models import (
    Project,
    Requirement,
    RequirementChunk,
    RequirementLink,
    RequirementVersion,
    User,
)
from app.integrations.llm.client import get_llm_client
from app.schemas.schemas import (
    RequirementCreate,
    RequirementLinkCreate,
    RequirementLinkResponse,
    RequirementListResponse,
    RequirementResponse,
    RequirementSearchHit,
    RequirementSearchRequest,
    RequirementSearchResponse,
    RequirementUpdate,
)

router = APIRouter(tags=["Requirements"])


async def verify_project_access(project_id: UUID, user: User, db: AsyncSession) -> Project:
    """Verify user has access to the project."""
    result = await db.execute(
        select(Project).where(
            Project.id == str(project_id),
            Project.tenant_id == user.tenant_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def get_requirement_or_404(requirement_id: UUID, user: User, db: AsyncSession) -> Requirement:
    """Load requirement and verify tenant access."""
    result = await db.execute(
        select(Requirement)
        .join(Project)
        .where(
            Requirement.id == str(requirement_id),
            Requirement.deleted_at.is_(None),
            Project.tenant_id == user.tenant_id,
            Project.deleted_at.is_(None),
        )
    )
    requirement = result.scalar_one_or_none()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement


def serialize_requirement_snapshot(requirement: Requirement) -> dict[str, Any]:
    """Serialize requirement content for immutable version snapshots."""
    return {
        "id": requirement.id,
        "tenant_id": requirement.tenant_id,
        "project_id": requirement.project_id,
        "key": requirement.key,
        "title": requirement.title,
        "description": requirement.description,
        "acceptance_criteria": requirement.acceptance_criteria,
        "business_rules": requirement.business_rules,
        "priority": requirement.priority,
        "status": requirement.status,
        "source_type": requirement.source_type,
        "source_ref": requirement.source_ref,
        "platform": requirement.platform,
        "version": requirement.version,
        "tags": requirement.tags,
        "metadata_json": requirement.metadata_json,
    }


def build_requirement_chunks(requirement: Requirement) -> list[dict[str, Any]]:
    """Build searchable chunks from a requirement."""
    chunks: list[dict[str, Any]] = []

    def add_chunk(chunk_type: str, content: str, metadata: dict[str, Any]) -> None:
        normalized = content.strip()
        if not normalized:
            return
        chunks.append(
            {
                "chunk_type": chunk_type,
                "content": normalized,
                "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "token_count": max(1, len(normalized) // 4),
                "metadata_json": metadata,
            }
        )

    add_chunk("title", requirement.title, {"field": "title"})

    for idx, paragraph in enumerate((requirement.description or "").splitlines()):
        if paragraph.strip():
            add_chunk("description", paragraph, {"field": "description", "paragraph_index": idx})

    for idx, criterion in enumerate(requirement.acceptance_criteria or []):
        add_chunk("acceptance", criterion, {"field": "acceptance_criteria", "item_index": idx})

    for idx, rule in enumerate(requirement.business_rules or []):
        add_chunk("rule", rule, {"field": "business_rules", "item_index": idx})

    return chunks


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def rebuild_requirement_index(
    requirement: Requirement,
    db: AsyncSession,
    *,
    try_embed: bool = True,
) -> list[RequirementChunk]:
    """Rebuild chunks and embeddings for the latest requirement version."""
    await db.execute(
        delete(RequirementChunk).where(
            RequirementChunk.requirement_id == requirement.id,
            RequirementChunk.version_no == requirement.version,
        )
    )

    llm_client = get_llm_client() if try_embed and settings.llm_api_key else None
    chunks: list[RequirementChunk] = []

    for index, chunk_data in enumerate(build_requirement_chunks(requirement)):
        embedding = None
        embedding_status = "pending"
        embedding_model = None

        if llm_client:
            try:
                embedding = await llm_client.create_embedding(chunk_data["content"])
                embedding_status = "ready"
                embedding_model = settings.llm_embedding_model
            except Exception:
                embedding_status = "failed"

        chunk = RequirementChunk(
            tenant_id=requirement.tenant_id,
            project_id=requirement.project_id,
            requirement_id=requirement.id,
            version_no=requirement.version,
            chunk_index=index,
            chunk_type=chunk_data["chunk_type"],
            content=chunk_data["content"],
            content_hash=chunk_data["content_hash"],
            token_count=chunk_data["token_count"],
            embedding=embedding,
            embedding_model=embedding_model,
            embedding_status=embedding_status,
            metadata_json=chunk_data["metadata_json"],
        )
        db.add(chunk)
        chunks.append(chunk)

    await db.flush()
    return chunks


async def create_requirement_version(
    requirement: Requirement,
    db: AsyncSession,
    *,
    created_by: str | None,
    change_log: str | None,
) -> RequirementVersion:
    """Persist an immutable requirement snapshot."""
    version = RequirementVersion(
        requirement_id=requirement.id,
        version_no=requirement.version,
        snapshot_json=serialize_requirement_snapshot(requirement),
        change_log=change_log,
        created_by=created_by,
    )
    db.add(version)
    await db.flush()
    return version


@router.post(
    "/projects/{project_id}/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    project_id: UUID,
    payload: RequirementCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new requirement under a project."""
    await verify_project_access(project_id, current_user, db)

    existing = await db.execute(
        select(Requirement).where(
            Requirement.project_id == str(project_id),
            Requirement.key == payload.key,
            Requirement.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requirement key already exists")

    requirement = Requirement(
        tenant_id=current_user.tenant_id,
        project_id=str(project_id),
        key=payload.key,
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
        business_rules=payload.business_rules,
        priority=payload.priority,
        status=payload.status,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        platform=payload.platform,
        tags=payload.tags,
        metadata_json=payload.metadata_json,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(requirement)
    await db.flush()

    await create_requirement_version(
        requirement,
        db,
        created_by=current_user.id,
        change_log=payload.change_log,
    )
    await rebuild_requirement_index(requirement, db)
    await db.refresh(requirement)
    return RequirementResponse.model_validate(requirement)


@router.get("/projects/{project_id}/requirements", response_model=RequirementListResponse)
async def list_requirements(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = Query(None),
    q: str | None = Query(None),
):
    """List requirements for a project."""
    await verify_project_access(project_id, current_user, db)

    base_query = select(Requirement).where(
        Requirement.project_id == str(project_id),
        Requirement.deleted_at.is_(None),
    )

    if status_filter:
        base_query = base_query.where(Requirement.status == status_filter)
    if priority:
        base_query = base_query.where(Requirement.priority == priority)
    if q:
        keyword = f"%{q.strip()}%"
        base_query = base_query.where(
            or_(
                Requirement.key.ilike(keyword),
                Requirement.title.ilike(keyword),
                cast(Requirement.description, Text).ilike(keyword),
                cast(Requirement.acceptance_criteria, Text).ilike(keyword),
                cast(Requirement.business_rules, Text).ilike(keyword),
            )
        )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)
    result = await db.execute(
        base_query.order_by(Requirement.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return RequirementListResponse(
        items=[RequirementResponse.model_validate(item) for item in items],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/requirements/{requirement_id}", response_model=RequirementResponse)
async def get_requirement(
    requirement_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a requirement by ID."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    return RequirementResponse.model_validate(requirement)


@router.patch("/requirements/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(
    requirement_id: UUID,
    payload: RequirementUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a requirement and rebuild its latest version index."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    update_data = payload.model_dump(exclude_unset=True, exclude={"change_log"})

    if "key" in update_data and update_data["key"] != requirement.key:
        existing = await db.execute(
            select(Requirement).where(
                Requirement.project_id == requirement.project_id,
                Requirement.key == update_data["key"],
                Requirement.id != requirement.id,
                Requirement.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requirement key already exists")

    if not update_data:
        return RequirementResponse.model_validate(requirement)

    for field, value in update_data.items():
        setattr(requirement, field, value)

    requirement.version += 1
    requirement.updated_by = current_user.id

    await db.flush()
    await create_requirement_version(
        requirement,
        db,
        created_by=current_user.id,
        change_log=payload.change_log,
    )
    await rebuild_requirement_index(requirement, db)
    await db.refresh(requirement)
    return RequirementResponse.model_validate(requirement)


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(
    requirement_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a requirement."""
    from datetime import datetime

    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    requirement.deleted_at = datetime.utcnow()
    await db.flush()


@router.post("/projects/{project_id}/requirements/search", response_model=RequirementSearchResponse)
async def search_requirements(
    project_id: UUID,
    payload: RequirementSearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Search requirements using pgvector when embeddings are available."""
    await verify_project_access(project_id, current_user, db)

    chunk_query = (
        select(RequirementChunk, Requirement)
        .join(Requirement, Requirement.id == RequirementChunk.requirement_id)
        .where(
            RequirementChunk.project_id == str(project_id),
            RequirementChunk.tenant_id == str(current_user.tenant_id),
            Requirement.deleted_at.is_(None),
            RequirementChunk.embedding.is_not(None),
            RequirementChunk.embedding_status == "ready",
        )
    )
    if payload.status:
        chunk_query = chunk_query.where(Requirement.status == payload.status)
    if payload.priority:
        chunk_query = chunk_query.where(Requirement.priority == payload.priority)
    if payload.platform:
        chunk_query = chunk_query.where(Requirement.platform.in_([payload.platform, "common"]))
    if payload.version:
        chunk_query = chunk_query.where(RequirementChunk.version_no == payload.version)
    else:
        chunk_query = chunk_query.where(RequirementChunk.version_no == Requirement.version)

    if settings.llm_api_key:
        try:
            query_embedding = await get_llm_client().create_embedding(payload.query)
            chunk_rows = (await db.execute(chunk_query)).all()
            if chunk_rows:
                aggregated: dict[str, dict[str, Any]] = {}
                for chunk, requirement in chunk_rows:
                    if not isinstance(chunk.embedding, list):
                        continue
                    score = cosine_similarity(query_embedding, [float(v) for v in chunk.embedding])
                    item = aggregated.setdefault(
                        requirement.id,
                        {
                            "requirement": requirement,
                            "score": score,
                            "matched_chunks": [],
                        },
                    )
                    item["score"] = max(item["score"], score)
                    if chunk.content not in item["matched_chunks"]:
                        item["matched_chunks"].append(chunk.content)

                ranked = [
                    value for value in sorted(aggregated.values(), key=lambda item: item["score"], reverse=True)
                    if value["score"] > 0
                ][: payload.top_k]

                if ranked:
                    hits = [
                        RequirementSearchHit(
                            requirement=RequirementResponse.model_validate(value["requirement"]),
                            score=value["score"],
                            matched_chunks=value["matched_chunks"][:3],
                        )
                        for value in ranked
                    ]
                    return RequirementSearchResponse(items=hits, total=len(hits))
        except Exception:
            pass

    keyword = f"%{payload.query.strip()}%"
    fallback_query = select(Requirement).where(
        Requirement.project_id == str(project_id),
        Requirement.deleted_at.is_(None),
        or_(
            Requirement.key.ilike(keyword),
            Requirement.title.ilike(keyword),
            cast(Requirement.description, Text).ilike(keyword),
            cast(Requirement.acceptance_criteria, Text).ilike(keyword),
            cast(Requirement.business_rules, Text).ilike(keyword),
        ),
    )
    if payload.status:
        fallback_query = fallback_query.where(Requirement.status == payload.status)
    if payload.priority:
        fallback_query = fallback_query.where(Requirement.priority == payload.priority)
    if payload.platform:
        fallback_query = fallback_query.where(Requirement.platform.in_([payload.platform, "common"]))
    if payload.version:
        fallback_query = fallback_query.where(Requirement.version == payload.version)

    requirements = (
        await db.execute(
            fallback_query.order_by(Requirement.updated_at.desc()).limit(payload.top_k)
        )
    ).scalars().all()

    hits = [
        RequirementSearchHit(
            requirement=RequirementResponse.model_validate(item),
            score=0.0,
            matched_chunks=[text_part for text_part in [item.title, item.description] if text_part][:2],
        )
        for item in requirements
    ]
    return RequirementSearchResponse(items=hits, total=len(hits))


@router.post(
    "/requirements/{requirement_id}/links",
    response_model=RequirementLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement_link(
    requirement_id: UUID,
    payload: RequirementLinkCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a traceability link for a requirement."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    existing = await db.execute(
        select(RequirementLink).where(
            RequirementLink.requirement_id == requirement.id,
            RequirementLink.target_type == payload.target_type,
            RequirementLink.target_id == str(payload.target_id),
            RequirementLink.link_type == payload.link_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requirement link already exists")

    link = RequirementLink(
        tenant_id=requirement.tenant_id,
        project_id=requirement.project_id,
        requirement_id=requirement.id,
        target_type=payload.target_type,
        target_id=str(payload.target_id),
        link_type=payload.link_type,
        confidence=payload.confidence,
        source=payload.source,
        metadata_json=payload.metadata_json,
        created_by=current_user.id,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return RequirementLinkResponse.model_validate(link)


@router.get("/requirements/{requirement_id}/links", response_model=list[RequirementLinkResponse])
async def list_requirement_links(
    requirement_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """List traceability links for a requirement."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    result = await db.execute(
        select(RequirementLink)
        .where(RequirementLink.requirement_id == requirement.id)
        .order_by(RequirementLink.created_at.desc())
    )
    return [RequirementLinkResponse.model_validate(item) for item in result.scalars().all()]


@router.delete("/requirements/{requirement_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement_link(
    requirement_id: UUID,
    link_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a traceability link."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    result = await db.execute(
        select(RequirementLink).where(
            RequirementLink.id == str(link_id),
            RequirementLink.requirement_id == requirement.id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement link not found")
    await db.delete(link)
    await db.flush()


@router.post("/requirements/{requirement_id}/reindex", response_model=RequirementResponse)
async def reindex_requirement(
    requirement_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Rebuild chunks and embeddings for the current requirement version."""
    requirement = await get_requirement_or_404(requirement_id, current_user, db)
    await rebuild_requirement_index(requirement, db)
    await db.refresh(requirement)
    return RequirementResponse.model_validate(requirement)