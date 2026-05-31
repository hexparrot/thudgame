"""Tests for the headless console CLI (console.py).

Covers the four subcommands and locks the documented README example
(``console.py next_move`` on start.thud -> TG7-F7) so the deliverable's
documentation stays trustworthy. Also pins the strict-validation behavior:
a malformed move line makes ``validate`` answer False rather than being
silently skipped.
"""

import logging
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Silence the engine's INFO logging during tests.
logging.disable(logging.CRITICAL)

import console

# The canonical opening position (matches start.thud / the README example).
START_HEADER = (
    'dF1,dG1,dJ1,dK1,dE2,dL2,dD3,dM3,dC4,dN4,dB5,dO5,dA6,dP6,dA7,dP7,'
    'dA9,dP9,dA10,dP10,dB11,dO11,dC12,dN12,dD13,dM13,dE14,dL14,dF15,'
    'dG15,dJ15,dK15,TG7,TH7,TJ7,TG8,TJ8,TG9,TH9,TJ9,RH8'
)


def _lines(name):
    with open(os.path.join(REPO_ROOT, name)) as f:
        return f.readlines()


class TestValidate:
    def test_legal_game_validates_true(self):
        assert console.cmd_validate([START_HEADER, 'dO11-O9']) == 'True'

    def test_malformed_move_line_validates_false(self):
        # 'dF15-07' has a zero where a file letter (A-P) belongs: it does not
        # parse, and a non-parsing move line must be reported, not skipped.
        assert console.cmd_validate([START_HEADER, 'dF15-07']) == 'False'

    def test_illegal_move_validates_false(self):
        # A parseable but illegal move (dwarf can't reach there) -> False.
        assert console.cmd_validate([START_HEADER, 'dF1-F1']) == 'False'

    def test_out_of_turn_validates_false(self):
        # Two dwarf moves in a row: the second is out of turn.
        assert console.cmd_validate([START_HEADER, 'dO11-O9', 'dN12-N9']) == 'False'

    def test_open_thud_fixture_validates_true(self):
        assert console.cmd_validate(_lines('open.thud')) == 'True'


class TestTurn:
    def test_dwarf_to_act_at_opening(self):
        assert console.cmd_turn([START_HEADER]) == 'dwarf'

    def test_troll_to_act_after_one_move(self):
        assert console.cmd_turn([START_HEADER, 'dO11-O9']) == 'troll'


class TestNextMove:
    def test_reproduces_documented_readme_example(self):
        # The README documents this exact result; lock it so the engine
        # heuristic can't silently drift away from the shipped docs.
        assert console.cmd_next_move([START_HEADER, 'dO11-O9']) == 'TG7-F7'


class TestCaptures:
    def test_returns_capture_from_last_move(self):
        # open.thud's final ply is a troll shove that captures: TJ8-L10xM9.
        assert console.cmd_captures(_lines('open.thud')) == 'TJ8-L10xM9'


class TestMain:
    def test_unknown_command_is_usage_error(self):
        assert console.main(['console.py', 'bogus']) == 2

    def test_missing_command_is_usage_error(self):
        assert console.main(['console.py']) == 2
