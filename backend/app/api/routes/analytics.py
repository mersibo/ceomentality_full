from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import Candidate, Drop
from app.schemas import AnalyticsDropOut, AnalyticsSummaryOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def date_filters(date_from: date | None, date_to: date | None):
    filters = []
    if date_from:
        filters.append(Candidate.applied_at >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to:
        filters.append(Candidate.applied_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC))
    return filters


async def count_candidates(session: SessionDep, filters: list, *conditions) -> int:
    return await session.scalar(
        select(func.count()).select_from(Candidate).where(*filters, *conditions)
    ) or 0


@router.get("/overview")
async def get_overview(
    session: SessionDep,
    user: CurrentUserDep,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    granularity: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    filters = date_filters(date_from, date_to)
    total = await count_candidates(session, filters)
    approved = await count_candidates(
        session, filters, Candidate.status.in_(["Approved", "Code assigned", "Code used", "Accepted"])
    )
    rejected = await count_candidates(session, filters, Candidate.status == "Rejected")
    under_review = await count_candidates(session, filters, Candidate.status == "Under review")
    codes_assigned = await count_candidates(session, filters, Candidate.code.is_not(None))
    codes_used = await count_candidates(session, filters, Candidate.status == "Code used")
    accepted = await count_candidates(session, filters, Candidate.status == "Accepted")
    purchases = await count_candidates(session, filters, Candidate.purchase_confirmed.is_(True))
    purchase_applications = await count_candidates(session, filters, Candidate.stage == "purchase")
    club_applications = await count_candidates(session, filters, Candidate.stage == "club")

    unit = {"daily": "day", "weekly": "week", "monthly": "month"}[granularity]
    bucket = func.date_trunc(unit, Candidate.applied_at).label("bucket")
    rows = (
        await session.execute(
            select(
                bucket,
                func.count().label("applications"),
                func.count().filter(
                    Candidate.status.in_(["Approved", "Code assigned", "Code used", "Accepted"])
                ).label("approved"),
                func.count().filter(Candidate.code.is_not(None)).label("codes"),
                func.count().filter(Candidate.status == "Code used").label("activated"),
            )
            .where(*filters)
            .group_by(bucket)
            .order_by(bucket)
        )
    ).all()

    drops = (await session.scalars(select(Drop).order_by(Drop.created_at.desc()))).all()
    drop_items = []
    for drop in drops:
        scoped = [*filters, Candidate.wave == drop.name]
        applications = await count_candidates(session, scoped)
        drop_approved = await count_candidates(
            session, scoped, Candidate.status.in_(["Approved", "Code assigned", "Code used", "Accepted"])
        )
        drop_rejected = await count_candidates(session, scoped, Candidate.status == "Rejected")
        issued = await count_candidates(session, scoped, Candidate.code.is_not(None))
        activated = await count_candidates(session, scoped, Candidate.status == "Code used")
        drop_items.append(
            {
                "dropId": drop.id,
                "dropName": drop.name,
                "status": drop.status,
                "validity": drop.validity,
                "applications": applications,
                "approved": drop_approved,
                "rejected": drop_rejected,
                "codesIssued": issued,
                "codesActivated": activated,
                "conversionRate": round((issued / applications) * 100, 2) if applications else 0,
            }
        )

    return {
        "summary": {
            "totalApplications": total,
            "approved": approved,
            "rejected": rejected,
            "underReview": under_review,
            "codesAssigned": codes_assigned,
            "codesUsed": codes_used,
            "accepted": accepted,
            "purchasesConfirmed": purchases,
            "conversionRate": round((codes_assigned / total) * 100, 2) if total else 0,
            "purchaseToClubConversion": round((club_applications / purchase_applications) * 100, 2)
            if purchase_applications
            else 0,
        },
        "timeseries": [
            {
                "date": row.bucket.date().isoformat(),
                "applications": row.applications,
                "approved": row.approved,
                "codesGenerated": row.codes,
                "codesActivated": row.activated,
                "conversionRate": round((row.codes / row.applications) * 100, 2) if row.applications else 0,
            }
            for row in rows
        ],
        "drops": drop_items,
    }


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_summary(session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    total_applications = await session.scalar(select(func.count()).select_from(Candidate)) or 0
    approved = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.status.in_(["Approved", "Accepted"]))
    ) or 0
    rejected = await session.scalar(select(func.count()).select_from(Candidate).where(Candidate.status == "Rejected")) or 0
    under_review = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.status == "Under review")
    ) or 0
    codes_assigned = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.code.is_not(None))
    ) or 0
    codes_used = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.status == "Code used")
    ) or 0
    conversion_rate = round((codes_assigned / total_applications) * 100, 2) if total_applications else 0.0

    return AnalyticsSummaryOut(
        totalApplications=total_applications,
        approved=approved,
        rejected=rejected,
        underReview=under_review,
        codesAssigned=codes_assigned,
        codesUsed=codes_used,
        conversionRate=conversion_rate,
    )


@router.get("/drops/{drop_id}", response_model=AnalyticsDropOut)
async def get_drop_analytics(drop_id: str, session: SessionDep, user: CurrentUserDep):
    if user.role not in {"founder", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    drop = await session.get(Drop, drop_id)
    if drop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drop not found")

    applications = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.wave == drop.name)
    ) or 0
    approved = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.wave == drop.name, Candidate.status.in_(["Approved", "Accepted"]))
    ) or 0
    rejected = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.wave == drop.name, Candidate.status == "Rejected")
    ) or 0
    users_with_access = await session.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.wave == drop.name, Candidate.code.is_not(None))
    ) or 0
    codes_issued = users_with_access

    return AnalyticsDropOut(
        dropId=drop.id,
        dropName=drop.name,
        applications=applications,
        approved=approved,
        rejected=rejected,
        codesIssued=codes_issued,
        usersWithAccess=users_with_access,
    )
