"""Tests for ``hermes auth status --all`` aggregated view."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hermes_cli import auth_commands


def _fake_get_auth_status_factory(table: dict[str, dict]):
    """Return a fake get_auth_status that looks up the *table* by provider id."""

    def _fake(provider_id: str | None = None) -> dict:
        return table.get(provider_id or "", {"logged_in": False})

    return _fake


def _args(*, all_flag: bool = False, provider: str | None = None, json_out: bool = False):
    return SimpleNamespace(all=all_flag, provider=provider, json=json_out)


@pytest.fixture
def patched_providers(monkeypatch):
    """Limit the provider universe to a small known set for deterministic output."""
    monkeypatch.setattr(
        auth_commands,
        "_iter_known_providers",
        lambda: ["anthropic", "openrouter", "spotify"],
    )
    return ["anthropic", "openrouter", "spotify"]


class TestAuthStatusAllHuman:
    def test_all_flag_prints_row_per_provider(self, monkeypatch, capsys, patched_providers):
        statuses = {
            "anthropic": {"logged_in": True, "auth_type": "api_key", "api_base_url": "https://api.anthropic.com"},
            "openrouter": {"logged_in": False},
            "spotify": {"logged_in": True, "expires_at": "2026-12-31T00:00:00Z"},
        }
        monkeypatch.setattr(
            "hermes_cli.auth.get_auth_status",
            _fake_get_auth_status_factory(statuses),
        )

        auth_commands.auth_status_command(_args(all_flag=True))
        out = capsys.readouterr().out

        # Header presence
        assert "provider" in out.lower()
        # All three providers appear
        assert "anthropic" in out
        assert "openrouter" in out
        assert "spotify" in out
        # Status indicators
        assert "logged in" in out or "yes" in out.lower()
        assert "logged out" in out or "no" in out.lower()

    def test_all_flag_includes_useful_detail(self, monkeypatch, capsys, patched_providers):
        statuses = {
            "anthropic": {"logged_in": True, "api_base_url": "https://api.anthropic.com"},
            "openrouter": {"logged_in": False, "error": "no key configured"},
            "spotify": {"logged_in": True, "expires_at": "2026-12-31T00:00:00Z"},
        }
        monkeypatch.setattr(
            "hermes_cli.auth.get_auth_status",
            _fake_get_auth_status_factory(statuses),
        )

        auth_commands.auth_status_command(_args(all_flag=True))
        out = capsys.readouterr().out

        # The error reason should surface for logged-out rows
        assert "no key configured" in out
        # Either expiry or base_url should surface for logged-in rows
        assert "anthropic.com" in out or "2026-12-31" in out


class TestAuthStatusAllJSON:
    def test_all_flag_with_json_emits_list(self, monkeypatch, capsys, patched_providers):
        statuses = {
            "anthropic": {"logged_in": True, "auth_type": "api_key"},
            "openrouter": {"logged_in": False},
            "spotify": {"logged_in": True, "expires_at": "2026-12-31T00:00:00Z"},
        }
        monkeypatch.setattr(
            "hermes_cli.auth.get_auth_status",
            _fake_get_auth_status_factory(statuses),
        )

        auth_commands.auth_status_command(_args(all_flag=True, json_out=True))
        payload = json.loads(capsys.readouterr().out)

        assert isinstance(payload, list)
        ids = {row["provider"] for row in payload}
        assert ids == {"anthropic", "openrouter", "spotify"}
        anth = next(r for r in payload if r["provider"] == "anthropic")
        assert anth["logged_in"] is True
        assert anth["auth_type"] == "api_key"


class TestAuthStatusBackwardCompat:
    def test_no_all_no_provider_exits(self, monkeypatch, capsys):
        with pytest.raises(SystemExit):
            auth_commands.auth_status_command(_args())

    def test_no_all_with_provider_keeps_old_output(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "hermes_cli.auth.get_auth_status",
            lambda p: {"logged_in": True, "auth_type": "api_key", "api_base_url": "https://x"},
        )

        auth_commands.auth_status_command(_args(provider="anthropic"))
        out = capsys.readouterr().out
        # Original per-provider format starts with "<provider>: logged in"
        assert "anthropic: logged in" in out
        assert "auth_type: api_key" in out
