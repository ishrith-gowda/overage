"""API route handlers for the Overage proxy.

Every endpoint is fully implemented with auth, validation, response models,
structured logging, and background task scheduling.
Reference: PRD.md Section 5 (API Contract), INSTRUCTIONS.md Section 11.
"""

import hashlib
import json
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from proxy.api.auth import validate_api_key
from proxy.config import get_settings
from proxy.estimation.aggregator import DiscrepancyAggregator
from proxy.estimation.palace import PALACEEstimator
from proxy.estimation.timing import TimingEstimator
from proxy.providers.base import ProviderRequest, provider_registry
from proxy.storage.database import get_db, get_session_factory
from proxy.storage.models import (
    APICallLog,
    APIKey,
    APIKeyCreate,
    APIKeyRead,
    DiscrepancyAlert,
    DiscrepancyAlertRead,
    ErrorResponse,
    EstimationResult,
    SummaryGroupRow,
    SummaryStats,
    SummaryWithGroups,
    TimeseriesPoint,
    User,
    UserCreate,
    UserRead,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["api"])

# Singletons injected by main.py lifespan
palace_estimator: PALACEEstimator | None = None
timing_estimator: TimingEstimator | None = None
aggregator: DiscrepancyAggregator | None = None


def set_estimators(
    palace: PALACEEstimator,
    timing: TimingEstimator,
    agg: DiscrepancyAggregator,
) -> None:
    """Set the estimation singletons. Called from main.py lifespan."""
    global palace_estimator, timing_estimator, aggregator  # noqa: PLW0603
    palace_estimator = palace
    timing_estimator = timing
    aggregator = agg


# ============================================================================
# Proxy endpoint — the core of Overage
# ============================================================================


@router.post(
    "/proxy/{provider_name}",
    response_model=None,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    summary="Proxy an LLM API call",
)
@router.post(
    "/proxy/{provider_name}/chat/completions",
    response_model=None,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    summary="OpenAI-compatible path (drop-in base_url for the OpenAI SDK)",
    include_in_schema=False,
)
@router.post(
    "/proxy/{provider_name}/v1/messages",
    response_model=None,
    responses={401: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    summary="Anthropic-compatible path (drop-in base_url for the Anthropic SDK)",
    include_in_schema=False,
)
async def proxy_request(
    provider_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(validate_api_key)],
    _session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse | JSONResponse:
    """Proxy an LLM API call, record timing, and queue estimation.

    The response is returned to the client immediately. Estimation and
    storage run asynchronously as background tasks.
    """
    log = logger.bind(provider=provider_name, user_id=current_user.id)
    body: dict[str, Any] = await request.json()

    provider = provider_registry.get(provider_name)
    model = body.get("model", "unknown")
    is_stream = body.get("stream", False)
    request_id: str = getattr(request.state, "request_id", "")

    # Build the normalized request
    provider_api_key = _extract_provider_key(request, provider_name)
    prov_request = ProviderRequest(
        provider=provider_name,
        model=model,
        messages=body.get("messages", []),
        raw_body=body,
        stream=is_stream,
        provider_api_key=provider_api_key,
    )

    if is_stream:
        prov_response, chunks = await provider.forward_streaming_request(prov_request)

        async def chunk_generator() -> AsyncGenerator[bytes]:
            for chunk in chunks:
                yield chunk

        # Schedule background estimation
        background_tasks.add_task(
            _record_and_estimate,
            user_id=current_user.id,
            provider_name=provider_name,
            model=prov_response.model,
            prov_response_dict=_response_to_dict(prov_response),
            body=body,
            request_id=request_id,
        )

        log.info("proxy_stream_complete", model=model, latency_ms=prov_response.total_latency_ms)
        return StreamingResponse(
            chunk_generator(),
            media_type="text/event-stream",
            headers={
                "X-Overage-Request-Id": request_id,
                "X-Overage-Latency-Added-Ms": "0",
            },
        )

    # Non-streaming
    prov_response = await provider.forward_request(prov_request)

    background_tasks.add_task(
        _record_and_estimate,
        user_id=current_user.id,
        provider_name=provider_name,
        model=prov_response.model,
        prov_response_dict=_response_to_dict(prov_response),
        body=body,
        request_id=request_id,
    )

    log.info("proxy_complete", model=model, latency_ms=round(prov_response.total_latency_ms, 2))
    return JSONResponse(
        content=prov_response.raw_response,
        headers={
            "X-Overage-Request-Id": request_id,
            "X-Overage-Latency-Added-Ms": str(round(prov_response.total_latency_ms, 1)),
        },
    )


# ============================================================================
# Calls listing and detail
# ============================================================================


@router.get("/calls", response_model=dict[str, Any], summary="List proxied calls")
async def list_calls(
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[str | None, Query(description="Filter by provider")] = None,
    model: Annotated[str | None, Query(description="Filter by model")] = None,
    start_date: Annotated[date | None, Query(description="Start date")] = None,
    end_date: Annotated[date | None, Query(description="End date")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """List API calls for the authenticated user with optional filtering."""
    stmt = select(APICallLog).where(APICallLog.user_id == current_user.id)

    if provider:
        stmt = stmt.where(APICallLog.provider == provider)
    if model:
        stmt = stmt.where(APICallLog.model == model)
    if start_date:
        stmt = stmt.where(
            APICallLog.timestamp >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        )
    if end_date:
        stmt = stmt.where(
            APICallLog.timestamp <= datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        )

    stmt = (
        stmt.options(selectinload(APICallLog.estimation))
        .order_by(APICallLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    calls = result.scalars().unique().all()

    # True total count for pagination
    count_stmt = select(func.count(APICallLog.id)).where(APICallLog.user_id == current_user.id)
    if provider:
        count_stmt = count_stmt.where(APICallLog.provider == provider)
    if model:
        count_stmt = count_stmt.where(APICallLog.model == model)
    if start_date:
        count_stmt = count_stmt.where(
            APICallLog.timestamp >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        )
    if end_date:
        count_stmt = count_stmt.where(
            APICallLog.timestamp <= datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        )
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    return {
        "calls": [_call_to_list_dict(c) for c in calls],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/calls/{call_id}", summary="Get call detail with estimation")
async def get_call_detail(
    call_id: int,
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get detailed information about a specific call including estimation results."""
    stmt = select(APICallLog).where(APICallLog.id == call_id, APICallLog.user_id == current_user.id)
    result = await session.execute(stmt)
    call = result.scalar_one_or_none()
    if call is None:
        return JSONResponse(
            status_code=404, content={"error": "Call not found", "error_code": "NOT_FOUND"}
        )  # type: ignore[return-value]

    # Fetch estimation row (separate query keeps SQL simple)
    est_stmt = select(EstimationResult).where(EstimationResult.call_id == call_id)
    est_result = await session.execute(est_stmt)
    estimation = est_result.scalar_one_or_none()

    return _call_detail_public_dict(call, estimation)


# ============================================================================
# Summary and timeseries
# ============================================================================


def _call_filter_conditions(
    user_id: int,
    provider: str | None,
    model: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[Any]:
    """Build WHERE fragments for API call queries (user + optional filters)."""
    conds: list[Any] = [APICallLog.user_id == user_id]
    if provider:
        conds.append(APICallLog.provider == provider)
    if model:
        conds.append(APICallLog.model == model)
    if start_date:
        conds.append(
            APICallLog.timestamp >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        )
    if end_date:
        conds.append(
            APICallLog.timestamp <= datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        )
    return conds


async def _fetch_summary_stats(
    session: AsyncSession,
    user_id: int,
    provider: str | None,
    model: str | None,
    start_date: date | None,
    end_date: date | None,
) -> SummaryStats:
    """Compute aggregate SummaryStats for the given filters."""
    stmt = (
        select(
            func.count(APICallLog.id).label("total_calls"),
            func.sum(APICallLog.reported_reasoning_tokens).label("total_reported"),
            func.sum(EstimationResult.combined_estimated_tokens).label("total_estimated"),
            func.avg(EstimationResult.discrepancy_pct).label("avg_discrepancy"),
            func.sum(EstimationResult.dollar_impact).label("total_dollars"),
            func.sum(
                case(
                    (
                        APICallLog.reported_reasoning_tokens.between(
                            EstimationResult.palace_confidence_low,
                            EstimationResult.palace_confidence_high,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("honoring_count"),
        )
        .outerjoin(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(and_(*_call_filter_conditions(user_id, provider, model, start_date, end_date)))
    )

    result = await session.execute(stmt)
    row = result.one()

    total_calls = row.total_calls or 0
    total_reported = row.total_reported or 0
    total_estimated = row.total_estimated or 0
    honoring_count = row.honoring_count or 0

    agg_pct = 0.0
    if total_estimated > 0:
        agg_pct = (total_reported - total_estimated) / total_estimated * 100.0

    honoring_rate = (honoring_count / total_calls * 100.0) if total_calls > 0 else 0.0

    return SummaryStats(
        total_calls=total_calls,
        total_reported_reasoning_tokens=total_reported,
        total_estimated_reasoning_tokens=total_estimated,
        aggregate_discrepancy_pct=round(agg_pct, 2),
        total_dollar_impact=round(float(row.total_dollars or 0), 2),
        avg_discrepancy_pct=round(float(row.avg_discrepancy or 0), 2),
        honoring_rate_pct=round(honoring_rate, 2),
    )


async def _fetch_summary_groups(
    session: AsyncSession,
    user_id: int,
    group_by: str,
    provider: str | None,
    model: str | None,
    start_date: date | None,
    end_date: date | None,
) -> list[SummaryGroupRow]:
    """Grouped aggregates for Story 8 (provider, model, or provider+model)."""
    filters = _call_filter_conditions(user_id, provider, model, start_date, end_date)
    join = APICallLog.id == EstimationResult.call_id

    agg = (
        func.count(APICallLog.id).label("total_calls"),
        func.sum(APICallLog.reported_reasoning_tokens).label("total_reported"),
        func.sum(EstimationResult.combined_estimated_tokens).label("total_estimated"),
        func.avg(EstimationResult.discrepancy_pct).label("avg_discrepancy"),
        func.sum(EstimationResult.dollar_impact).label("total_dollars"),
    )

    if group_by == "provider":
        stmt = (
            select(APICallLog.provider, *agg)
            .outerjoin(EstimationResult, join)
            .where(and_(*filters))
            .group_by(APICallLog.provider)
            .order_by(APICallLog.provider)
        )
    elif group_by == "model":
        stmt = (
            select(APICallLog.model, *agg)
            .outerjoin(EstimationResult, join)
            .where(and_(*filters))
            .group_by(APICallLog.model)
            .order_by(APICallLog.model)
        )
    else:
        stmt = (
            select(APICallLog.provider, APICallLog.model, *agg)
            .outerjoin(EstimationResult, join)
            .where(and_(*filters))
            .group_by(APICallLog.provider, APICallLog.model)
            .order_by(APICallLog.provider, APICallLog.model)
        )

    result = await session.execute(stmt)
    rows = result.all()
    out: list[SummaryGroupRow] = []
    for row in rows:
        if group_by == "provider":
            p, tc, trp, te, ad, td = (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
            )
            gkey = str(p)
            prov: str | None = str(p)
            mdl: str | None = None
        elif group_by == "model":
            m, tc, trp, te, ad, td = row[0], row[1], row[2], row[3], row[4], row[5]
            gkey = str(m)
            prov = None
            mdl = str(m)
        else:
            p, m, tc, trp, te, ad, td = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            gkey = f"{p}::{m}"
            prov = str(p)
            mdl = str(m)

        tc = int(tc or 0)
        trp = int(trp or 0)
        te = int(te or 0)
        agg_pct = 0.0
        if te > 0:
            agg_pct = (trp - te) / te * 100.0

        out.append(
            SummaryGroupRow(
                group_key=gkey,
                provider=prov,
                model=mdl,
                call_count=tc,
                total_reported_reasoning_tokens=trp,
                total_estimated_reasoning_tokens=te,
                aggregate_discrepancy_pct=round(agg_pct, 2),
                avg_discrepancy_pct=round(float(ad or 0), 2),
                total_dollar_impact=round(float(td or 0), 4),
                low_confidence=tc < 10,
            )
        )
    return out


@router.get(
    "/summary",
    summary="Aggregate discrepancy stats (optional group_by for per-provider/model breakdown)",
)
async def get_summary(
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[str | None, Query()] = None,
    model: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    group_by: Annotated[
        str | None,
        Query(
            description="If set: provider | model | provider_model (PRD Story 8). "
            "Returns overall + groups."
        ),
    ] = None,
) -> SummaryStats | SummaryWithGroups:
    """Get aggregate statistics; optional ``group_by`` adds grouped breakdown rows."""
    if group_by is not None and group_by not in ("provider", "model", "provider_model"):
        raise HTTPException(
            status_code=422,
            detail="group_by must be one of: provider, model, provider_model",
        )

    overall = await _fetch_summary_stats(
        session,
        current_user.id,
        provider,
        model,
        start_date,
        end_date,
    )
    if group_by is None:
        return overall

    groups = await _fetch_summary_groups(
        session,
        current_user.id,
        group_by,
        provider,
        model,
        start_date,
        end_date,
    )
    return SummaryWithGroups(overall=overall, groups=groups)


@router.get("/summary/timeseries", summary="Daily time-series data")
async def get_timeseries(
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> dict[str, Any]:
    """Get daily aggregated time-series data for charts."""
    sd = start_date or (datetime.now(tz=UTC).date() - timedelta(days=30))
    ed = end_date or datetime.now(tz=UTC).date()

    stmt = (
        select(
            func.date(APICallLog.timestamp).label("day"),
            func.count(APICallLog.id).label("call_count"),
            func.sum(APICallLog.reported_reasoning_tokens).label("reported"),
            func.sum(EstimationResult.combined_estimated_tokens).label("estimated"),
            func.avg(EstimationResult.discrepancy_pct).label("discrepancy"),
            func.sum(EstimationResult.dollar_impact).label("dollars"),
        )
        .outerjoin(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(APICallLog.user_id == current_user.id)
        .where(APICallLog.timestamp >= datetime.combine(sd, datetime.min.time(), tzinfo=UTC))
        .where(APICallLog.timestamp <= datetime.combine(ed, datetime.max.time(), tzinfo=UTC))
        .group_by(func.date(APICallLog.timestamp))
        .order_by(func.date(APICallLog.timestamp))
    )

    result = await session.execute(stmt)
    rows = result.all()

    points = [
        TimeseriesPoint(
            date=str(row.day),
            call_count=row.call_count or 0,
            reported_reasoning_tokens=row.reported or 0,
            estimated_reasoning_tokens=row.estimated or 0,
            discrepancy_pct=round(float(row.discrepancy or 0), 2),
            dollar_impact=round(float(row.dollars or 0), 2),
        ).model_dump()
        for row in rows
    ]

    return {"data": points, "period": {"start_date": str(sd), "end_date": str(ed)}}


@router.get("/report", summary="Download PDF audit report for a date range (PRD Story 6)")
async def get_audit_report(
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    start_date: Annotated[date, Query(description="Period start (inclusive, UTC)")],
    end_date: Annotated[date, Query(description="Period end (inclusive, UTC)")],
) -> Response:
    """Generate a branded PDF with aggregates, breakdowns, top calls, and a time-series chart."""
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be on or after start_date")

    max_days = 366
    if (end_date - start_date).days > max_days:
        raise HTTPException(
            status_code=422,
            detail=f"Date range must not exceed {max_days} days",
        )

    from proxy.reporting.data import load_audit_report_bundle
    from proxy.reporting.pdf_audit import render_audit_pdf

    uid = current_user.id
    user_label = current_user.email or f"user_{uid}"
    bundle = await load_audit_report_bundle(session, uid, user_label, start_date, end_date)
    pdf_bytes = render_audit_pdf(bundle)
    filename = f"overage-audit-{start_date}-{end_date}.pdf"

    logger.info(
        "audit_report_generated",
        user_id=current_user.id,
        start_date=str(start_date),
        end_date=str(end_date),
        total_calls=bundle.overall.total_calls,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/alerts", summary="List discrepancy alerts for the current user")
async def list_alerts(
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by alert_status: active | acknowledged | resolved | all"),
    ] = "active",
) -> dict[str, Any]:
    """Return stored discrepancy alerts (PRD Story 9 data model; listing in MVP)."""
    stmt = select(DiscrepancyAlert).where(DiscrepancyAlert.user_id == current_user.id)
    if status and status != "all":
        stmt = stmt.where(DiscrepancyAlert.alert_status == status)
    stmt = stmt.order_by(DiscrepancyAlert.created_at.desc())
    result = await session.execute(stmt)
    alerts = result.scalars().all()
    serialized = [DiscrepancyAlertRead.model_validate(a).model_dump(mode="json") for a in alerts]
    return {"alerts": serialized, "total": len(serialized)}


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=DiscrepancyAlertRead,
    summary="Acknowledge a discrepancy alert",
)
async def acknowledge_alert(
    alert_id: int,
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiscrepancyAlertRead:
    """Mark an alert as acknowledged (idempotent if already acknowledged)."""
    result = await session.execute(
        select(DiscrepancyAlert).where(
            DiscrepancyAlert.id == alert_id,
            DiscrepancyAlert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.alert_status != "acknowledged":
        alert.alert_status = "acknowledged"
        alert.acknowledged_at = datetime.now(tz=UTC)
        await session.flush()

    logger.info("alert_acknowledged", alert_id=alert_id, user_id=current_user.id)
    return DiscrepancyAlertRead.model_validate(alert)


# ============================================================================
# Auth endpoints
# ============================================================================


@router.post("/auth/register", response_model=UserRead, status_code=201, summary="Register user")
async def register_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """Create a new user account."""
    # Check for existing email
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        return JSONResponse(
            status_code=409,
            content={"error": "Email already registered", "error_code": "DUPLICATE_EMAIL"},
        )  # type: ignore[return-value]

    # Hash password (simple SHA-256 for MVP — use bcrypt for production)
    pwd_hash = hashlib.sha256(payload.password.encode()).hexdigest()

    user = User(email=payload.email, name=payload.name, password_hash=pwd_hash)
    session.add(user)
    await session.flush()

    # Auto-generate an API key for the new user
    raw_key, key_hash = APIKey.generate_key()
    api_key = APIKey(user_id=user.id, key_hash=key_hash, name="Default Key")
    session.add(api_key)

    logger.info("user_registered", user_id=user.id, email=payload.email)

    user_data = UserRead.model_validate(user).model_dump(mode="json")
    user_data["api_key"] = raw_key
    return JSONResponse(status_code=201, content=user_data)  # type: ignore[return-value]


@router.post("/auth/apikey", response_model=APIKeyRead, status_code=201, summary="Generate API key")
async def generate_api_key(
    payload: APIKeyCreate,
    current_user: Annotated[User, Depends(validate_api_key)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> APIKeyRead:
    """Generate a new API key for the authenticated user."""
    raw_key, key_hash = APIKey.generate_key()
    api_key = APIKey(user_id=current_user.id, key_hash=key_hash, name=payload.name)
    session.add(api_key)
    await session.flush()

    logger.info("api_key_generated", user_id=current_user.id, key_id=api_key.id)
    return APIKeyRead(key=raw_key, name=api_key.name, created_at=api_key.created_at)


# ============================================================================
# Background task: record call and run estimation
# ============================================================================


async def _record_and_estimate(
    user_id: int,
    provider_name: str,
    model: str,
    prov_response_dict: dict[str, Any],
    body: dict[str, Any],
    request_id: str,
) -> None:
    """Background task: store call log, run estimation, store result.

    Runs after the proxy response is sent to the client.
    """
    log = logger.bind(user_id=user_id, provider=provider_name, request_id=request_id)

    try:
        factory = get_session_factory()
        async with factory() as session:
            # Build prompt hash (privacy: never store raw prompt)
            prompt_text = json.dumps(body.get("messages", []))
            prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()

            call_log = APICallLog(
                user_id=user_id,
                provider=provider_name,
                model=model,
                prompt_hash=prompt_hash,
                prompt_length_chars=len(prompt_text),
                answer_length_chars=0,
                reported_input_tokens=prov_response_dict.get("input_tokens", 0),
                reported_output_tokens=prov_response_dict.get("output_tokens", 0),
                reported_reasoning_tokens=prov_response_dict.get("reasoning_tokens", 0),
                total_latency_ms=prov_response_dict.get("total_latency_ms", 0),
                ttft_ms=prov_response_dict.get("ttft_ms"),
                is_streaming=prov_response_dict.get("is_streaming", False),
                raw_usage_json=json.dumps(prov_response_dict.get("raw_usage", {})),
                request_id=request_id,
            )
            session.add(call_log)
            await session.flush()

            # Run estimation only when enabled (PALACE may use deterministic placeholder
            # when weights are missing; see proxy/estimation/palace.py).
            settings = get_settings()
            if settings.estimation_enabled and palace_estimator and timing_estimator and aggregator:
                palace_pred = await palace_estimator.predict(prompt_text[:2000], "")
                timing_est = await timing_estimator.estimate(
                    model=model,
                    latency_ms=call_log.total_latency_ms,
                    output_tokens_non_reasoning=call_log.reported_output_tokens
                    - call_log.reported_reasoning_tokens,
                )

                # Update timing window
                await timing_estimator.profile_update(
                    model=model,
                    reported_tokens=call_log.reported_output_tokens,
                    latency_ms=call_log.total_latency_ms,
                )

                agg = aggregator.aggregate_single_call(
                    reported_reasoning_tokens=call_log.reported_reasoning_tokens,
                    provider=provider_name,
                    model=model,
                    palace_prediction=palace_pred,
                    timing_estimate=timing_est,
                )

                estimation = EstimationResult(
                    call_id=call_log.id,
                    palace_estimated_tokens=agg.palace_estimated_tokens,
                    palace_confidence_low=agg.palace_confidence_low,
                    palace_confidence_high=agg.palace_confidence_high,
                    palace_model_version=agg.palace_model_version,
                    timing_estimated_tokens=agg.timing_estimated_tokens,
                    timing_tps_used=agg.timing_tps_used,
                    timing_r_squared=agg.timing_r_squared,
                    combined_estimated_tokens=agg.combined_estimated_tokens,
                    discrepancy_pct=agg.discrepancy_pct,
                    dollar_impact=agg.dollar_impact,
                    signals_agree=agg.signals_agree,
                    domain_classification=agg.domain_classification,
                )
                session.add(estimation)

                await aggregator.record_discrepancy(user_id, agg.discrepancy_pct, agg.dollar_impact)

            await session.commit()
            log.info("call_recorded", call_id=call_log.id)

    except Exception as exc:
        log.error("background_record_failed", error=str(exc))


# ============================================================================
# Helpers
# ============================================================================


def _extract_provider_key(request: Request, provider_name: str) -> str:
    """Extract the provider API key from the request headers."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # Anthropic uses x-api-key header
    if provider_name == "anthropic":
        return request.headers.get("x-api-key", "")
    return ""


def _response_to_dict(resp: Any) -> dict[str, Any]:
    """Convert a ProviderResponse to a serializable dict."""
    return {
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "reasoning_tokens": resp.reasoning_tokens,
        "total_latency_ms": resp.total_latency_ms,
        "ttft_ms": resp.ttft_ms,
        "is_streaming": resp.is_streaming,
        "raw_usage": resp.raw_usage,
    }


def _call_to_dict(call: APICallLog) -> dict[str, Any]:
    """Serialize an APICallLog to a dict for API responses."""
    return {
        "id": call.id,
        "provider": call.provider,
        "model": call.model,
        "reported_input_tokens": call.reported_input_tokens,
        "reported_output_tokens": call.reported_output_tokens,
        "reported_reasoning_tokens": call.reported_reasoning_tokens,
        "total_latency_ms": call.total_latency_ms,
        "ttft_ms": call.ttft_ms,
        "is_streaming": call.is_streaming,
        "timestamp": call.timestamp.isoformat() if call.timestamp else None,
        "request_id": call.request_id,
    }


def _call_to_list_dict(call: APICallLog) -> dict[str, Any]:
    """Serialize a call for GET /v1/calls including estimation summary when present."""
    row: dict[str, Any] = _call_to_dict(call)
    est = call.estimation
    if est is not None:
        row["estimated_reasoning_tokens"] = est.combined_estimated_tokens
        row["discrepancy_pct"] = round(est.discrepancy_pct, 4)
        row["timing_r_squared"] = est.timing_r_squared
        row["timing_estimated_tokens"] = est.timing_estimated_tokens
        row["signals_agree"] = est.signals_agree
        row["dollar_impact"] = round(est.dollar_impact, 6)
    else:
        row["estimated_reasoning_tokens"] = None
        row["discrepancy_pct"] = None
        row["timing_r_squared"] = None
        row["timing_estimated_tokens"] = None
        row["signals_agree"] = None
        row["dollar_impact"] = None
    return row


def _estimation_to_dict(est: EstimationResult) -> dict[str, Any]:
    """Serialize an EstimationResult to a dict for API responses."""
    return {
        "palace_estimated_tokens": est.palace_estimated_tokens,
        "palace_confidence_low": est.palace_confidence_low,
        "palace_confidence_high": est.palace_confidence_high,
        "palace_model_version": est.palace_model_version,
        "timing_estimated_tokens": est.timing_estimated_tokens,
        "timing_tps_used": est.timing_tps_used,
        "timing_r_squared": est.timing_r_squared,
        "combined_estimated_tokens": est.combined_estimated_tokens,
        "discrepancy_pct": est.discrepancy_pct,
        "dollar_impact": est.dollar_impact,
        "signals_agree": est.signals_agree,
        "domain_classification": est.domain_classification,
        "estimated_at": est.estimated_at.isoformat() if est.estimated_at else None,
    }


def _call_detail_public_dict(
    call: APICallLog,
    estimation: EstimationResult | None,
) -> dict[str, Any]:
    """Build PRD §5 flat JSON for ``GET /v1/calls/{call_id}``."""
    try:
        parsed = json.loads(call.raw_usage_json or "{}")
    except json.JSONDecodeError:
        parsed = {}
    raw_usage_json: dict[str, Any] = parsed if isinstance(parsed, dict) else {}

    return {
        "id": call.id,
        "provider": call.provider,
        "model": call.model,
        "endpoint": call.endpoint,
        "prompt_hash": call.prompt_hash,
        "prompt_length_chars": call.prompt_length_chars,
        "answer_length_chars": call.answer_length_chars,
        "reported_input_tokens": call.reported_input_tokens,
        "reported_output_tokens": call.reported_output_tokens,
        "reported_reasoning_tokens": call.reported_reasoning_tokens,
        "total_latency_ms": call.total_latency_ms,
        "ttft_ms": call.ttft_ms,
        "is_streaming": call.is_streaming,
        "raw_usage_json": raw_usage_json,
        "timestamp": call.timestamp.isoformat() if call.timestamp else None,
        "request_id": call.request_id,
        "estimation": _estimation_to_dict(estimation) if estimation else None,
    }
