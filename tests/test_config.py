"""Tests for admin-id parsing and is_admin (env-driven config)."""

import pytest

from bot.utils.config import ConfigLoader


def test_parse_admin_ids_various_separators(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "111, 222;333")
    assert ConfigLoader._parse_admin_ids() == {111, 222, 333}


def test_parse_admin_ids_empty(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "")
    assert ConfigLoader._parse_admin_ids() == set()


def test_parse_admin_ids_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert ConfigLoader._parse_admin_ids() == set()


def test_parse_admin_ids_invalid_raises(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "111,notanid")
    with pytest.raises(ValueError):
        ConfigLoader._parse_admin_ids()


def test_is_admin_uses_env(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "555,666")
    loader = ConfigLoader()
    assert loader.is_admin(555) is True
    assert loader.is_admin(666) is True
    assert loader.is_admin(999) is False


def test_admin_ids_cached_until_reload(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "1")
    loader = ConfigLoader()
    assert loader.get_admin_ids() == [1]
    # Cached: changing env without reload() has no effect.
    monkeypatch.setenv("ADMIN_IDS", "1,2,3")
    assert loader.get_admin_ids() == [1]
    loader.reload()
    assert set(loader.get_admin_ids()) == {1, 2, 3}
