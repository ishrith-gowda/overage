"""API key validation and rate limiting for FastAPI dependency injection.

Validates the X-API-Key header, looks up the user, and enforces rate limits.
Reference: INSTRUCTIONS.md Section 11 (API Endpoint Patterns).
"""

import time
from collections import defaultdict
from typing import Annotated

import structlog
from fastapi import Depends, Header
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from proxy.config import get_settings
from proxy.exceptions import InvalidAPIKeyError, RateLimitExceededError
from proxy.storage.database import get_db
from proxy.storage.models import APIKey, User, utcnow

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory sliding window rate limiter
# Per-key → list of timestamps (seconds). Entries older than the window
# are evicted on each check.
# For multi-instance deployments, replace with Redis-backed counter.
# ---------------------------------------------------------------------------
_rate_limit_windows: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(key_hash: str) -> None:
    """Enforce per-key rate limiting using an in-memory sliding window.

    Args:
        key_hash: The hashed API key (used as the rate limit key).

    Raises:
        RateLimitExceededError: If the key has exceeded its rate limit.
    """
    settings = get_settings()
    limit = settings.rate_limit_per_minute
    window_seconds = 60.0
    now = time.monotonic()

    # Evict expired entries
    entries = _rate_limit_windows[key_hash]
    cutoff = now - window_seconds
    _rate_limit_windows[key_hash] = [t for t in entries if t > cutoff]

    if len(_rate_limit_windows[key_hash]) >= limit:
        raise RateLimitExceededError(limit=limit, window_seconds=int(window_seconds))

    _rate_limit_windows[key_hash].append(now)


async def validate_api_key(
    session: Annotated[AsyncSession, Depends(get_db)],
    x_api_key: Annotated[str | None, Header(description="Overage API key")] = None,
) -> User:
    """FastAPI dependency: validate the API key and return the authenticated User.

    Steps:
    1. Hash the incoming key with SHA-256.
    2. Look up the hash in the api_keys table.
    3. Verify the key is active.
    4. Enforce rate limiting.
    5. Update last_used_at timestamp.
    6. Return the associated User.

    Args:
        x_api_key: The raw API key from the X-API-Key header.
        session: The database session (injected).

    Returns:
        The authenticated User object.

    Raises:
        InvalidAPIKeyError: If the key is missing, invalid, or inactive.
        RateLimitExceededError: If the key has exceeded its rate limit.
    """
    if not x_api_key:
        raise InvalidAPIKeyError

    key_hash = APIKey.hash_key(x_api_key)

    # Look up the key and join to the user
    stmt = (
        select(User, APIKey)
        .join(APIKey, User.id == APIKey.user_id)
        .where(APIKey.key_hash == key_hash)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()

    if row is None:
        logger.warning("auth_invalid_key", key_prefix=x_api_key[:12])
        raise InvalidAPIKeyError

    user, api_key = row.tuple()

    if not api_key.is_active:
        logger.warning("auth_inactive_key", user_id=user.id, key_id=api_key.id)
        raise InvalidAPIKeyError

    # Rate limiting
    _check_rate_limit(key_hash)

    # Update last_used_at (fire-and-forget, don't block the response)
    await session.execute(
        update(APIKey).where(APIKey.id == api_key.id).values(last_used_at=utcnow())
    )

    logger.debug("auth_success", user_id=user.id, key_id=api_key.id)
    return user
