"""Tests for RateLimitService (atomic consume + DB fallback)."""

from bot.services.rate_limit import get_rate_limit_service
from bot.services.user_service import get_user_service
from bot.services.submission_service import get_submission_service


async def test_try_acquire_enforces_daily_limit():
    svc = get_rate_limit_service()
    limit = svc.limit  # config default: 2
    user_id = 3001

    results = [await svc.try_acquire(user_id) for _ in range(limit + 1)]

    # First `limit` succeed with increasing counts, the next is rejected.
    for i in range(limit):
        assert results[i][0] is True
        assert results[i][1] == i + 1
    assert results[limit][0] is False


async def test_rejected_acquire_rolls_back_counter():
    svc = get_rate_limit_service()
    user_id = 3002
    for _ in range(svc.limit + 3):
        await svc.try_acquire(user_id)

    # The counter must be clamped at the limit (rollbacks applied), not inflated.
    assert await svc.get_count(user_id) == svc.limit


async def test_check_limit_reports_state():
    svc = get_rate_limit_service()
    user_id = 3003
    allowed, count = await svc.check_limit(user_id)
    assert allowed is True and count == 0

    await svc.try_acquire(user_id)
    allowed, count = await svc.check_limit(user_id)
    assert count == 1


async def test_db_fallback_when_redis_down(monkeypatch):
    svc = get_rate_limit_service()
    user_id = 3004
    await get_user_service().get_or_create_user(user_id)

    class _BrokenClient:
        async def incr(self, *a, **k):
            raise RuntimeError("redis down")

        async def get(self, *a, **k):
            raise RuntimeError("redis down")

    class _BrokenManager:
        def get_client(self):
            return _BrokenClient()

    monkeypatch.setattr(svc, "redis", _BrokenManager())

    # No submissions yet -> still allowed via DB count.
    allowed, _ = await svc.try_acquire(user_id)
    assert allowed is True

    # Fill the DB up to the limit -> fallback must now reject.
    sub_svc = get_submission_service()
    for _ in range(svc.limit):
        await sub_svc.create_submission(user_id=user_id, show_authorship=False)

    allowed, _ = await svc.try_acquire(user_id)
    assert allowed is False
