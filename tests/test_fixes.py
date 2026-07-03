"""Regression tests for the crash / hang / rules fixes (see FIXUP.MD).

Each class maps to a finding ID. Grouped by layer: engine (E*), server (S*),
console (C*), plus the scored-terminal and self-play API added for ML.
"""

import asyncio
import io
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.disable(logging.CRITICAL)

from thud import ai_engine, selfplay
from thud.ai_engine import AIEngine
from thud.bitboard import Bitboard
from thud.gameboard import Gameboard
from thud.ply import NoMoveException, Ply


def _pos(file, rank):
    return rank * 17 + file


# ----- E8: Bitboard bounds ---------------------------------------------------
class TestBitboardBounds:
    def test_negative_position_raises(self):
        with pytest.raises(ValueError):
            Bitboard([-1])

    def test_huge_negative_position_raises_not_allocates(self):
        # The DoS vector: this used to allocate a ~10 GB integer.
        with pytest.raises(ValueError):
            Bitboard([-10 ** 9])

    def test_oversize_position_raises(self):
        with pytest.raises(ValueError):
            Bitboard([Bitboard.N])

    def test_getitem_out_of_range_returns_zero(self):
        bb = Bitboard([5])
        assert bb[Bitboard.N] == 0      # was: negative shift -> ValueError
        assert bb[-1] == 0

    def test_in_range_construction_still_works(self):
        assert len(Bitboard([0, 5, 288])) == 3


# ----- E6: notation validation ----------------------------------------------
class TestNotationValidation:
    def test_off_board_position_to_notation_raises(self):
        with pytest.raises(ValueError):
            Ply.position_to_notation(0)      # file 0 / rank 0

    def test_bad_file_letter_raises(self):
        with pytest.raises(ValueError):
            Ply.notation_to_position('Z9')

    def test_out_of_range_rank_parse_returns_none(self):
        assert Ply.parse_string('dA0-A16') is None
        assert Ply.parse_string('dA16-B2') is None

    def test_bad_capture_notation_returns_none(self):
        assert Ply.parse_string('TG7-F7xZ9') is None

    def test_valid_notation_still_round_trips(self):
        assert str(Ply.parse_string('TG7-F7xE7')) == 'TG7-F7xE7'


# ----- E1: boxed-in troll no longer loops forever ---------------------------
class TestBoxedTrollTerminates:
    def test_fully_enclosed_troll_returns_no_move(self):
        g = Gameboard('classic')
        t = _pos(8, 5)
        g.trolls = Bitboard([t])
        g.dwarfs = Bitboard([t - 18, t - 17, t - 16, t - 1,
                             t + 1, t + 16, t + 17, t + 18])
        # A hang here would time the test out; [] is the correct result.
        assert AIEngine(g).nonoptimal_troll_moves() == []


# ----- E3: no-move raises NoMoveException, not StopIteration -----------------
class TestNoMoveRaisesCleanly:
    def test_sealed_dwarf_kvt_raises_nomove(self):
        g = Gameboard('kvt')
        d = _pos(1, 8)
        g.dwarfs = Bitboard([d])
        g.trolls = Bitboard([_pos(1, 7), _pos(1, 9),
                             _pos(2, 7), _pos(2, 8), _pos(2, 9)])
        with pytest.raises(NoMoveException):
            AIEngine.calculate_best_move(g, 'dwarf', 0)


# ----- E4: filter_best with negative scores ---------------------------------
class TestFilterBest:
    def test_variance_returns_truthy_with_negative_scores(self):
        g = Gameboard('classic')
        t = _pos(8, 5)
        g.trolls = Bitboard([t])  # troll material score is negative here
        cands = [Ply('troll', t, t + 17, []), Ply('troll', t, t + 1, [])]
        assert bool(AIEngine(g).filter_best('troll', cands, variance_pct=0.1))

    def test_empty_candidates_returns_falsy(self):
        assert not AIEngine(Gameboard('classic')).filter_best('troll', [])


# ----- E5: outcome checks on degenerate boards ------------------------------
class TestOutcomeDegenerateBoards:
    def test_klash_zero_dwarfs_no_crash(self):
        g = Gameboard('klash')
        g.dwarfs = Bitboard()
        g.ply_list.append(Ply('dwarf', _pos(6, 2), _pos(6, 3), []))
        assert g.get_game_outcome() in (None, 'dwarf', 'troll')

    def test_kvt_no_thudstone_no_crash(self):
        g = Gameboard('kvt')
        g.thudstone = Bitboard()
        g.ply_list.append(Ply('dwarf', _pos(8, 9), _pos(8, 8), []))
        assert g.get_game_outcome() in (None, 'dwarf', 'troll')


# ----- E7: null-move + thudstone gating -------------------------------------
class TestNullMoveAndThudstoneGate:
    def test_empty_origin_move_is_illegal(self):
        g = Gameboard('classic')
        empty_a, empty_b = _pos(8, 5), _pos(8, 4)
        assert g.token_at(empty_a) == 'empty'
        assert g.validate_move(empty_a, empty_b) == (False, False, [])

    def test_classic_thudstone_is_immovable(self):
        g = Gameboard('classic')
        g.trolls = Bitboard()
        g.dwarfs = Bitboard([_pos(7, 8), _pos(9, 8), _pos(7, 7), _pos(9, 7)])
        move, _, _ = g.validate_move(_pos(8, 8), _pos(8, 7))
        assert move is False


# ----- E11: klash materialization -------------------------------------------
class TestKlashMaterialization:
    def test_find_materializations_yields_central_squares(self):
        g = Gameboard('klash')
        mats = list(g.find_materializations())
        assert mats and all(m.origin == m.dest for m in mats)

    def test_apply_ply_materialization_adds_troll(self):
        g = Gameboard('klash')
        g.apply_ply(next(iter(g.find_materializations())))
        assert len(g.trolls) == 1
        assert g.klash_trolls == 1

    def test_klash_ai_can_take_a_troll_turn(self):
        g = Gameboard('klash')
        d = AIEngine.calculate_best_move(g, 'dwarf', 0)
        g.apply_ply(d)
        g.ply_list.append(d)
        t = AIEngine.calculate_best_move(g, 'troll', 0)  # used to raise NoMove
        assert t.token == 'troll'


# ----- E2 / R1: scored terminal ---------------------------------------------
class TestScoredTerminal:
    def test_ongoing_game_is_none(self):
        assert Gameboard('classic').result() is None

    def test_rout_is_scored_win(self):
        g = Gameboard('classic')
        g.trolls = Bitboard()
        g.ply_list.append(Ply('dwarf', _pos(6, 1), _pos(6, 2), []))  # troll to act
        term = g.result()
        assert term['winner'] == 'dwarf'
        assert term['reason'] == 'win'
        assert term['score'] == 4 * 0 - len(g.dwarfs)

    def test_cutoff_is_scored(self):
        g = Gameboard('classic')
        term = g.result(max_plies=0)  # already at the cap
        assert term['reason'] == 'cutoff'
        assert term['winner'] in ('dwarf', 'troll', 'draw')

    def test_troll_material_weight_is_4_to_1(self):
        g = Gameboard('classic')
        assert g.troll_material() == 4 * 8 - 32


# ----- E10 / termination: self-play driver ----------------------------------
class TestSelfPlayTerminates:
    @pytest.mark.parametrize('ruleset', ['classic', 'kvt', 'klash'])
    def test_game_terminates_with_score(self, ruleset):
        r = selfplay.play_game(ruleset, seed=7, max_plies=80)
        assert r['winner'] in ('dwarf', 'troll', 'draw')
        assert isinstance(r['score'], int)
        assert r['reason'] in ('win', 'no-move', 'cutoff')

    def test_classic_seed_1006_no_attributeerror(self):
        # E10: this seed previously crashed at ply 36 with AttributeError.
        r = selfplay.play_game('classic', seed=1006, max_plies=400)
        assert r['winner'] in ('dwarf', 'troll', 'draw')

    def test_seeded_selfplay_is_reproducible(self):
        a = selfplay.play_game('classic', seed=123, max_plies=120)
        b = selfplay.play_game('classic', seed=123, max_plies=120)
        assert [str(p) for p in a['ply_list']] == [str(p) for p in b['ply_list']]


# ----- snapshot / restore ---------------------------------------------------
class TestSnapshotRestore:
    def test_restore_undoes_a_ply(self):
        g = Gameboard('classic')
        fresh = Gameboard('classic')
        snap = g.snapshot()
        m = AIEngine.calculate_best_move(g, 'dwarf', 0)
        g.apply_ply(m)
        g.ply_list.append(m)
        g.restore(snap)
        assert g.dwarfs == fresh.dwarfs
        assert g.trolls == fresh.trolls
        assert len(g.ply_list) == 0


# ----- S1 / S2: server move guards ------------------------------------------
class _FakeWS:
    def __init__(self):
        self.closed = False
        self.sent = []

    async def send_str(self, s):
        self.sent.append(s)


def _seat(role):
    import server
    server.GAME = server.GameSession()
    ws = _FakeWS()
    server.GAME.clients.add(ws)
    if role == 'dwarf':
        server.GAME.dwarf_ws = ws
    elif role == 'troll':
        server.GAME.troll_ws = ws
    return server, ws


class TestServerMoveGuards:
    def test_out_of_range_origin_rejected(self):
        server, ws = _seat('dwarf')
        asyncio.run(server._handle_move(ws, {'origin': -10 ** 9, 'dest': _pos(7, 2)}))
        assert any('out of range' in m for m in ws.sent)
        assert len(server.GAME.board.ply_list) == 0

    def test_moving_opponent_piece_rejected(self):
        server, ws = _seat('dwarf')  # dwarf to act at the opening
        troll_sq = _pos(7, 7)
        asyncio.run(server._handle_move(ws, {'origin': troll_sq, 'dest': _pos(6, 6)}))
        assert any('your own pieces' in m for m in ws.sent)
        assert len(server.GAME.board.ply_list) == 0

    def test_legal_own_move_applies(self):
        server, ws = _seat('dwarf')
        origin = Ply.notation_to_position('F1')
        dest = Ply.notation_to_position('G2')
        asyncio.run(server._handle_move(ws, {'origin': origin, 'dest': dest}))
        assert len(server.GAME.board.ply_list) == 1


# ----- C1 / C2: console error handling --------------------------------------
_START_HEADER = (
    'dF1,dG1,dJ1,dK1,dE2,dL2,dD3,dM3,dC4,dN4,dB5,dO5,dA6,dP6,dA7,dP7,'
    'dA9,dP9,dA10,dP10,dB11,dO11,dC12,dN12,dD13,dM13,dE14,dL14,dF15,'
    'dG15,dJ15,dK15,TG7,TH7,TJ7,TG8,TJ8,TG9,TH9,TJ9,RH8'
)


class TestConsoleErrorHandling:
    def test_next_move_terminal_emits_sentinel(self, monkeypatch, capsys):
        import console

        def _raise(*a, **k):
            raise NoMoveException('troll')

        monkeypatch.setattr(console.AIEngine, 'calculate_best_move', _raise)
        monkeypatch.setattr(sys, 'stdin', io.StringIO(_START_HEADER + '\n'))
        rc = console.main(['console.py', 'next_move'])
        out = capsys.readouterr().out
        assert rc == 0
        assert 'no-move:troll' in out

    def test_turn_on_malformed_input_fails_loudly(self, monkeypatch, capsys):
        import console
        monkeypatch.setattr(sys, 'stdin',
                            io.StringIO(_START_HEADER + '\nBADMOVE\n'))
        rc = console.main(['console.py', 'turn'])
        err = capsys.readouterr().err
        assert rc == 1
        assert 'error' in err
