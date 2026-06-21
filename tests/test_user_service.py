"""Tests for UserService."""

from bot.services.user_service import get_user_service


async def test_create_then_update_does_not_clobber_with_none():
    svc = get_user_service()
    await svc.get_or_create_user(1001, username="alice", first_name="Alice")

    # A later /start without a username must not erase the stored one.
    user = await svc.get_or_create_user(1001, username=None, first_name="Alice")
    assert user.username == "alice"
    assert user.first_name == "Alice"


async def test_update_overwrites_when_value_provided():
    svc = get_user_service()
    await svc.get_or_create_user(1002, username="old")
    user = await svc.get_or_create_user(1002, username="new")
    assert user.username == "new"


async def test_increment_submission_count_is_atomic():
    svc = get_user_service()
    await svc.get_or_create_user(1003)
    await svc.increment_submission_count(1003)
    await svc.increment_submission_count(1003)
    user = await svc.get_user(1003)
    assert user.total_submissions_count == 2


async def test_block_unblock_and_is_blocked():
    svc = get_user_service()
    await svc.get_or_create_user(1004)
    assert await svc.is_blocked(1004) is False

    assert await svc.block_user(1004) is True
    assert await svc.is_blocked(1004) is True

    assert await svc.unblock_user(1004) is True
    assert await svc.is_blocked(1004) is False


async def test_is_blocked_unknown_user():
    svc = get_user_service()
    assert await svc.is_blocked(999999) is False


async def test_get_usernames_map():
    svc = get_user_service()
    await svc.get_or_create_user(1005, username="bob")
    await svc.get_or_create_user(1006, username=None)
    mapping = await svc.get_usernames([1005, 1006, 1007])
    assert mapping == {1005: "bob", 1006: None}
