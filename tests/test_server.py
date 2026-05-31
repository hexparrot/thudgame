"""Tests for the multiplayer server's synchronous slot/permission logic.

``GameSession`` mutates only plain attributes via identity comparison, so
the seat-allocation and reset-permission rules can be unit-tested without
the aiohttp event loop. The live WebSocket protocol is covered separately
by the manual integration smoke described in the review plan.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import GameSession


def ws():
    """A stand-in WebSocket: GameSession only ever compares these by identity."""
    return object()


class TestAutoAssign:
    def test_first_two_get_sides_third_spectates(self):
        s = GameSession()
        a, b, c = ws(), ws(), ws()
        s.auto_assign(a)
        s.auto_assign(b)
        s.auto_assign(c)
        assert s.role_of(a) == 'dwarf'
        assert s.role_of(b) == 'troll'
        assert s.role_of(c) == 'spectator'

    def test_unseated_connection_is_spectator(self):
        s = GameSession()
        assert s.role_of(ws()) == 'spectator'


class TestCanReset:
    def test_players_can_reset(self):
        s = GameSession()
        a, b = ws(), ws()
        s.auto_assign(a)
        s.auto_assign(b)
        assert s.can_reset(a) is True
        assert s.can_reset(b) is True

    def test_spectator_cannot_reset(self):
        s = GameSession()
        a, b, spectator = ws(), ws(), ws()
        s.auto_assign(a)
        s.auto_assign(b)
        s.auto_assign(spectator)  # no slot left
        assert s.can_reset(spectator) is False


class TestClaimReleaseSwap:
    def test_claim_open_side(self):
        s = GameSession()
        a = ws()
        assert s.try_claim(a, 'troll') is True
        assert s.role_of(a) == 'troll'

    def test_claim_taken_side_fails(self):
        s = GameSession()
        a, b = ws(), ws()
        assert s.try_claim(a, 'dwarf') is True
        assert s.try_claim(b, 'dwarf') is False
        assert s.role_of(b) == 'spectator'

    def test_swap_sides_releases_old_slot(self):
        s = GameSession()
        a = ws()
        s.try_claim(a, 'dwarf')
        assert s.try_claim(a, 'troll') is True
        assert s.role_of(a) == 'troll'
        assert s.dwarf_ws is None  # old slot freed by the swap

    def test_release_frees_slot(self):
        s = GameSession()
        a = ws()
        s.try_claim(a, 'dwarf')
        s.release(a)
        assert s.role_of(a) == 'spectator'
        assert s.dwarf_ws is None

    def test_invalid_side_rejected(self):
        s = GameSession()
        assert s.try_claim(ws(), 'goblin') is False


class TestPayloads:
    def test_players_payload_counts_spectators(self):
        s = GameSession()
        a, b, c = ws(), ws(), ws()
        for conn in (a, b, c):
            s.clients.add(conn)
            s.auto_assign(conn)
        payload = s.players_payload()
        assert payload['dwarf_taken'] is True
        assert payload['troll_taken'] is True
        assert payload['spectator_count'] == 1

    def test_state_payload_reports_opening(self):
        s = GameSession()
        payload = s.state_payload()
        assert payload['turn'] == 'dwarf'
        assert payload['winner'] is None
        assert payload['ruleset'] == 'classic'
        assert len(payload['board']['dwarfs']) == 32
        assert len(payload['board']['trolls']) == 8
