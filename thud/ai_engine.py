"""AIEngine — heuristic move chooser for both sides.

Per-call lifecycle: a fresh ``AIEngine`` is constructed around a board
snapshot (deep-copied so simulation can mutate freely without touching
the caller's state). The engine then either evaluates a specific ply
(``apply`` / ``score`` / ``predict_future``) or asks
``calculate_best_move`` to pick one.

Logging goes through the module-level ``ai_log`` logger (level INFO).
"""

import copy
import itertools
import logging
import math
import random

from .bitboard import Bitboard
from .influence_map import InfluenceMap
from .ply import NoMoveException, Ply


ai_log = logging.getLogger('ai_logger')
ai_log.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
ai_log.addHandler(_handler)


class AIEngine(object):
    def __init__(self, board):
        self.board = copy.deepcopy(board)
        self.moves = []
        self.threats = []
        self.setups = []

    def apply(self, ply_list):
        """Apply a sequence of plies to the engine's internal board."""
        for p in ply_list:
            self.board.apply_ply(p)
            self.board.ply_list.append(p)

    def score(self, token):
        """Material-only score: trolls count quadruple, dwarfs count single."""
        if token == 'troll':
            score = len(self.board.trolls) * 4 - len(self.board.dwarfs)
        else:
            score = len(self.board.dwarfs) - len(self.board.trolls) * 4
        return score

    def filter_adjacent_threats(self, token):
        """Return capture-plies that eliminate dwarfs adjacent to our trolls.

        Adjacency loses 4 points immediately if a troll is left next to a
        dwarf on the dwarf's turn, so this should be considered first.
        Dwarf side is intentionally unhandled (the heuristic only makes
        sense for the side that can be captured by a single move).
        """
        if token != 'troll':
            return []

        adjacent_threats = set()
        for t in self.board.trolls.get_bits():
            adjacent_threats.update(self.board.tokens_adjacent(t, 'dwarf'))

        solutions = []
        for j in adjacent_threats:
            for t in self.threats:
                if j in t.captured:
                    solutions.append(t)
        return solutions

    def filter_capture_destinations(self, ply_list):
        """Return the unique set of destination squares from a list of plies."""
        return list({p.dest for p in ply_list})

    def find_line_blocks(self):
        """Return dwarf plies that block the front of a troll shove line.

        Considers both the immediately-adjacent block square and one off,
        which makes it harder for a non-line troll to nibble the blocker
        without breaking the shove.
        """
        empties = set()

        for ply in self.board.find_caps('troll'):
            shove_direction = self.board.get_direction(ply.origin, ply.dest)
            opposite_direction = self.board.get_direction(ply.dest, ply.origin)

            for i in range(3):
                if self.board.token_at(ply.origin + (opposite_direction * i)) != 'troll':
                    break
            else:
                empties.add(ply.origin + shove_direction)
                empties.add(ply.origin + shove_direction + shove_direction)

        available_blockers = list(self.filter_dwarfs_can_reach(empties))
        best_blockers = self.filter_farthest_dwarfs(available_blockers, 0.1)
        return best_blockers

    def filter_threatened_pieces(self, friendly_token):
        """Count friendly pieces the opponent could capture next turn."""
        def is_threatened(pos):
            if self.board.trolls[pos]:
                for i in self.board.dwarfs.get_bits():
                    if self.board.validate_move(i, pos, False, True)[1]:
                        return True
            elif self.board.dwarfs[pos]:
                for i in self.board.trolls.get_bits():
                    direction = self.board.get_direction(i, pos)
                    if self.board.validate_move(i, i + direction, False, True)[1]:
                        return True

        pieces = {'troll': self.board.trolls,
                  'dwarf': self.board.dwarfs}[friendly_token]
        count = 0
        for i in pieces.get_bits():
            if is_threatened(i):
                count += 1
        return count

    def nonoptimal_troll_moves(self):
        """Pick troll moves that close distance to the nearest dwarf."""
        def alternate_direction(general_direction):
            """If our preferred square is blocked, pick a related direction
            with at least one vector preserved. Only reached when a troll
            is otherwise immobilized (e.g., next to the thudstone)."""
            candidates = []
            significant_vector_f = general_direction[0] or 0
            significant_vector_r = general_direction[1] or 0

            if significant_vector_f and significant_vector_r:
                candidates.append((significant_vector_f, 0))
                candidates.append((0, significant_vector_r))
            elif significant_vector_f:
                candidates.append((significant_vector_f, -1))
                candidates.append((significant_vector_f, 1))
            elif significant_vector_r:
                candidates.append((-1, significant_vector_r))
                candidates.append((1, significant_vector_r))
            return random.choice(candidates)

        lowest = 100
        candidates = []

        for t in self.board.trolls.get_bits():
            for d in self.board.dwarfs.get_bits():
                hypotenuse = Ply.calc_pythagoras(t, d)
                if hypotenuse < lowest:
                    lowest = hypotenuse
                    candidates = []
                if hypotenuse == lowest:
                    delta = self.board.get_delta(Ply.position_to_tuple(t),
                                                 Ply.position_to_tuple(d))
                    direction = self.board.delta_to_direction(delta)
                    while self.board.token_at(t + direction) != 'empty':
                        delta = alternate_direction(delta)
                        direction = self.board.delta_to_direction(delta)
                    candidates.append(Ply('troll', t, t + direction, []))
        return candidates

    def filter_dwarfs_can_reach(self, dense_spots):
        """Yield plies from ``self.moves`` whose dest is in ``dense_spots``."""
        for d in dense_spots:
            for m in self.moves:
                if d == m.dest:
                    yield m

    def filter_farthest_dwarfs(self, ply_list, variance=.4):
        """Filter to plies whose distance is within ``variance`` of the max.

        This avoids the AI repeatedly nudging dwarfs by 1-2 squares; a
        minimum threshold of √2 (one diagonal step) is enforced.
        """
        farthest = 0
        candidates = []

        for i in ply_list:
            farthest = max(farthest, Ply.calc_pythagoras(i.origin, i.dest))

        if farthest <= math.sqrt(2):
            return []

        for i in ply_list:
            if Ply.calc_pythagoras(i.origin, i.dest) >= farthest * (1 - variance):
                candidates.append(i)
        return candidates

    def filter_best(self, token, candidates, variance_pct=0):
        """Pick a random ply from those within ``variance_pct`` of the best score."""
        for p in candidates:
            scratch = AIEngine(self.board)
            scratch.apply((p,))
            p.score = scratch.score(token)
        candidates = sorted(candidates, key=lambda v: v.score, reverse=True)

        top = list(filter(
            lambda p: p.score >= candidates[0].score * (1 - variance_pct),
            candidates))
        if top:
            return random.choice(top)
        return Ply(None, None, None, None)

    @staticmethod
    def predict_future(board, firstply, lookahead, token):
        """Apply ``firstply``, then auto-play ``lookahead`` moves; return ``token``'s score."""
        b = AIEngine(board)
        b.apply((firstply,))
        for i in range(1, lookahead + 1):
            try:
                result = AIEngine.calculate_best_move(b.board, b.board.turn_to_act(), 0)
                assert result
                b.apply((result,))
            except NoMoveException:
                break
        return b.score(token)

    @staticmethod
    def select_best_future(board, plies, lookahead, token):
        """Of all candidate plies, return the one with the best predicted future."""
        best_score = -101
        best_ply = None
        for ply in plies:
            score = AIEngine.predict_future(board, ply, lookahead, token)
            if score > best_score:
                best_score = score
                best_ply = ply
        return best_ply

    @staticmethod
    def calculate_best_move(board, token, lookahead=0):
        """Return ``token``'s best move on ``board``, optionally with a lookahead.

        Raises ``NoMoveException`` if the side has been wiped or no move
        can be chosen.
        """
        decision = None
        best_move = None

        b = AIEngine(board)

        if not len(b.board.dwarfs):
            raise NoMoveException('dwarf')
        elif not len(b.board.trolls):
            raise NoMoveException('troll')

        if token == 'troll':
            ai_log.info('TROLL')
            ai_log.info('turn: %d', len(b.board.ply_list) / 2)
            b.threats = list(b.board.find_caps(token))
            b.setups = list(b.board.find_setups(token))

            immediate_threats = b.filter_adjacent_threats(token)
            if immediate_threats:
                decision = b.filter_best(token, immediate_threats)
                ai_log.info('save %i %s', decision.score, decision or 'x')
            else:
                tsb = AIEngine.select_best_future(
                    b.board, itertools.chain(b.threats, b.setups), 0, token)
                if tsb:
                    decision = tsb
                else:
                    decision = b.filter_best(token, b.nonoptimal_troll_moves())

            ai_log.info('# threats: %i', len(b.threats))
            ai_log.debug('%s', ', '.join(str(s) for s in b.threats))
            ai_log.info('# setups: %i', len(b.setups))
            ai_log.debug('%s', ', '.join(str(s) for s in b.setups))
            ai_log.info('  T: %i d: %i\n', len(b.board.trolls) * 4, len(b.board.dwarfs))
        elif token == 'dwarf':
            ai_log.info('DWARF')
            ai_log.info('turn: %d', len(b.board.ply_list) / 2)

            b.threats = list(b.board.find_caps(token))

            decision = b.filter_best(token, b.threats)
            ai_log.info('best cap %i %s', decision.score, decision or 'x')

            if not decision:
                troll_cd = b.filter_capture_destinations(list(b.board.find_caps('troll')))
                b.setups = list(b.board.find_setups(token, Bitboard(troll_cd)))
                b.moves = list(b.board.find_moves(token))
                b.blocks = list(b.find_line_blocks())

                tsb = AIEngine.select_best_future(
                    b.board,
                    itertools.chain(b.threats, b.setups, b.blocks),
                    lookahead, token)

                imap = InfluenceMap(b.board.dwarfs, b.board.trolls)
                empties_adjacent = []
                for i in [.05, .15, .25]:
                    for d in imap.highest(i):
                        empties_adjacent.extend(b.board.tokens_adjacent(d, 'empty'))
                    candidates = list(b.filter_dwarfs_can_reach(empties_adjacent))
                    candidates = b.filter_farthest_dwarfs(candidates)
                    if not candidates:
                        continue
                    else:
                        best_move = b.filter_best(token, candidates)
                        break

                if tsb:
                    decision = AIEngine.select_best_future(
                        b.board, [tsb, best_move], lookahead, token)
                elif best_move:
                    decision = best_move
                else:
                    decision = next(b.board.find_moves('dwarf'))

            ai_log.info('# threats: %i', len(list(b.threats)))
            ai_log.debug('%s', ', '.join(str(s) for s in b.threats))
            ai_log.info('# setups: %i', len(b.setups))
            ai_log.debug('%s', ', '.join(str(s) for s in b.setups))
            ai_log.info('# moves: %i', len(b.moves))
            ai_log.info('  T: %i d: %i\n', len(b.board.trolls) * 4, len(b.board.dwarfs))

        if not decision:
            raise NoMoveException(token)
        return decision
