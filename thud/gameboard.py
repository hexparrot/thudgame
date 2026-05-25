"""Gameboard — board state, rules, and legal-move enumeration.

Owns the four Bitboards that constitute a position (``trolls``, ``dwarfs``,
``thudstone``, ``playable``) plus the move history (``ply_list``) and a
sticky ``game_winner`` once an outcome is reached. Pure rules layer: no
AI, no I/O.

Three rulesets are supported: ``classic`` (the canonical game),
``kvt`` (Koom Valley Thud — moveable thudstone, troll multi-captures),
and ``klash``.
"""

import copy

from .bitboard import Bitboard
from .ply import Ply


class Gameboard:
    def __init__(self, ruleset='classic'):
        self.BOARD_WIDTH = Bitboard.BOARD_WIDTH
        self.ruleset = ruleset
        self.ply_list = []
        self.game_winner = None
        self.klash_trolls = 0

        self.playable = self.get_default_board('playable', ruleset)
        self.trolls = self.get_default_board('troll', ruleset)
        self.dwarfs = self.get_default_board('dwarf', ruleset)
        self.thudstone = self.get_default_board('thudstone', ruleset)

    def turn_to_act(self):
        """Return the token of the side allowed to move now.

        Classic/Klash alternate strictly. KVT trolls may multi-capture,
        which is handled by extra rules in validate_move; this method
        still returns the nominal side-to-move.
        """
        return len(self.ply_list) % 2 and 'troll' or 'dwarf'

    def display(self, board):
        """Print the 17x17 bitboard in row-major form (debug helper)."""
        for i, v in enumerate(str(board)):
            if not i % self.BOARD_WIDTH:
                print()
            print(str(v).rjust(2), end='')

    def get_default_positions(self, token, ruleset):
        """Return the starting positions of ``token`` for ``ruleset``.

        The result is a tuple of integer positions, in the order the
        underlying list literal was written (which file_savegame relies on
        for readable .thud output).
        """
        def playable():
            if ruleset == 'klash':
                dist_from_center = [0,0,2,3,4,5,6,6,6,6,6,5,4,3,2,0,0]
            else:
                dist_from_center = [0,2,3,4,5,6,7,7,7,7,7,6,5,4,3,2,0]
            pos = []
            for i, v in enumerate(dist_from_center):
                if v:
                    for j in range(-v, v + 1):
                        pos.append((i, (self.BOARD_WIDTH // 2) + j))
            return pos

        if token == 'playable':
            notations = playable()
        elif token == 'thudstone':
            notations = [(8, 8)]
        elif token == 'troll':
            notations = {
                'classic': [(7,7),(8,7),(9,7),
                            (7,8),      (9,8),
                            (7,9),(8,9),(9,9)],
                'kvt': [(6,2),(8,2),(10,2),
                        (5,3),(6,3),(8,3),(10,3),(11,3)],
                'klash': []
                }[ruleset]
        elif token == 'dwarf':
            notations = {
                'classic': [(6,1), (7,1), (9,1), (10,1),
                            (5,2), (11,2),(4,3), (12,3),
                            (3,4), (13,4),(2,5), (14,5),
                            (1,6), (15,6),(1,7), (15,7),
                            (1,9), (15,9),(1,10),(15,10),
                            (2,11),(14,11),(3,12),(13,12),
                            (4,13),(12,13),(5,14),(11,14),
                            (6,15),(7,15), (9,15),(10,15)],
                'kvt': [(8,9), (1,10),(15,10),
                        (2,11),(14,11),
                        (3,12),(13,12),
                        (4,13),(12,13),
                        (5,14),(11,14),
                        (6,15),(7,15), (8,15),(9,15),(10,15)],
                'klash': [(6,2), (7,2), (9,2), (10,2),
                          (5,3), (11,3),
                          (3,5), (13,5),
                          (2,6), (14,6),
                          (2,7), (14,7),
                          (2,9), (14,9),
                          (2,10),(14,10),
                          (3,11),(13,11),
                          (5,13),(11,13),
                          (6,14),(10,14),
                          (7,14),(9,14)]
                }[ruleset]
        else:
            raise ValueError("unknown token type: {!r}".format(token))

        return tuple(map(Ply.tuple_to_position, notations))

    def get_default_board(self, board_type, ruleset='classic'):
        """Return a Bitboard with all default positions for token/ruleset."""
        return Bitboard(self.get_default_positions(board_type, ruleset))

    def occupied_squares(self):
        """Union Bitboard of all squares currently occupied by any piece."""
        return self.dwarfs | self.trolls | self.thudstone

    def token_at(self, position):
        """Return 'troll' / 'dwarf' / 'thudstone' / 'empty' / None at position."""
        if self.trolls[position]:
            return 'troll'
        elif self.dwarfs[position]:
            return 'dwarf'
        elif self.thudstone[position]:
            return 'thudstone'
        elif self.playable[position]:
            return 'empty'

    def add_troll(self, pos):
        """Klash-only: add a troll at ``pos`` and bump the materialized count."""
        self.trolls |= Bitboard([pos])
        self.klash_trolls += 1

    def apply_ply(self, ply):
        """Apply ``ply`` to the underlying bitboards (no validation)."""
        if ply.token == 'troll':
            self.trolls = self.trolls & ~Bitboard([ply.origin]) | Bitboard([ply.dest])
            self.dwarfs = self.dwarfs & ~Bitboard(ply.captured)
        elif ply.token == 'dwarf':
            self.dwarfs = self.dwarfs & ~Bitboard([ply.origin]) | Bitboard([ply.dest])
            self.trolls = self.trolls & ~Bitboard(ply.captured)
        elif ply.token == 'thudstone':
            self.thudstone = self.thudstone & ~Bitboard([ply.origin]) | Bitboard([ply.dest])

    def cycle_direction(self):
        """Yield all 8 king-move direction offsets (in integer-position units)."""
        for i in [-self.BOARD_WIDTH-1, -self.BOARD_WIDTH, -self.BOARD_WIDTH+1,
                  self.BOARD_WIDTH-1, self.BOARD_WIDTH, self.BOARD_WIDTH+1,
                  -1, 1]:
            yield i

    def get_delta(self, origin, dest):
        """Return general direction tuple in {-1,0,1} x {-1,0,1}."""
        delta_file = (dest[0] > origin[0]) - (dest[0] < origin[0])
        delta_rank = (dest[1] > origin[1]) - (dest[1] < origin[1])
        return (delta_file, delta_rank)

    def delta_to_direction(self, delta):
        """Translate a (df,dr) delta into a 1-step integer-position offset."""
        return {
            (-1,-1): -self.BOARD_WIDTH-1,
            ( 0,-1): -self.BOARD_WIDTH,
            ( 1,-1): -self.BOARD_WIDTH+1,
            (-1, 0): -1,
            ( 0, 0): 0,
            ( 1, 0): 1,
            (-1, 1): self.BOARD_WIDTH-1,
            ( 0, 1): self.BOARD_WIDTH,
            ( 1, 1): self.BOARD_WIDTH+1
            }[delta]

    def get_direction(self, origin, dest):
        """Discrete 1-step direction from ``origin`` toward ``dest``."""
        delta = self.get_delta(Ply.position_to_tuple(origin), Ply.position_to_tuple(dest))
        return self.delta_to_direction(delta)

    def check_if_all(self, seq, token):
        """True if every item in ``seq`` equals ``token``."""
        return all(x == token for x in seq)

    def get_range(self, origin, dest):
        """Return the list of tokens along the line from ``origin`` to ``dest`` (inclusive)."""
        direction = self.get_direction(origin, dest)
        return [self.token_at(i) for i in range(origin, dest + direction, direction)]

    def tokens_adjacent(self, position, token):
        """Return positions of pieces of type ``token`` adjacent to ``position``."""
        return [position + d for d in self.cycle_direction()
                if self.token_at(position + d) == token]

    def validate_move(self, origin, dest, testmoves=True, testcaps=True):
        """Determine whether a move from ``origin`` to ``dest`` is legal.

        Returns a 3-tuple ``(is_valid_move, is_valid_capture, captured)``.
        Caller must check ``is_materializing`` separately for Klash troll
        materialization (origin == dest).
        """
        def is_materializing(origin, dest):
            if (origin == dest
                    and (len(self.ply_list) % 2 and 'troll')
                    and self.token_at(origin) == 'empty'
                    and origin in self.get_default_positions('troll', 'classic')):
                return True

        def is_dumb(origin, dest):
            try:
                origin_bb = Bitboard([origin])
                dest_bb = Bitboard([dest])
            except (TypeError, ValueError):
                return True
            if not (origin_bb & self.playable):
                return True
            if not (dest_bb & self.playable):
                return True
            if origin == dest:
                return True
            t_origin = Ply.position_to_tuple(origin)
            t_dest = Ply.position_to_tuple(dest)
            df = t_origin[0] - t_dest[0]
            dr = t_origin[1] - t_dest[1]
            if df and dr and abs(df) != abs(dr):
                return True
            return False

        def must_be_jump(position):
            """KVT: after a troll capture, that troll may only jump again."""
            if (self.ply_list
                    and self.ply_list[-1].token == 'troll'
                    and self.ply_list[-1].captured
                    and self.trolls[position]):
                return True

        def is_valid_cap_kvt(origin, dest):
            capturable = []
            if self.dwarfs[origin]:
                for i in self.tokens_adjacent(dest, 'troll'):
                    direction = self.get_direction(dest, i)
                    seq = self.get_range(dest, dest + direction + direction)
                    if seq == ['empty', 'troll', 'dwarf']:
                        capturable.append(dest + direction)
                return capturable
            elif self.trolls[origin]:
                if self.get_range(origin, dest) == ['troll', 'dwarf', 'empty']:
                    return [origin + self.get_direction(origin, dest)]
            return []

        def is_valid_cap_normal(origin, dest):
            if self.dwarfs[origin]:
                seq = self.get_range(origin, dest)
                if seq.pop(-1) == 'troll' and seq.pop(0) == 'dwarf':
                    if not len(seq):
                        return [dest]
                    if self.check_if_all(seq, 'empty'):
                        direction = self.get_direction(dest, origin)
                        if is_dumb(origin, origin + direction * len(seq)):
                            return []
                        newseq = self.get_range(origin, origin + direction * len(seq))
                        if self.check_if_all(newseq, 'dwarf'):
                            return [dest]
            elif self.trolls[origin]:
                seq = self.get_range(origin, dest)
                if seq.pop(-1) == 'empty' and seq.pop(0) == 'troll':
                    capturable = self.tokens_adjacent(dest, 'dwarf')
                    if not capturable:
                        return []
                    elif not seq:
                        return capturable
                    elif self.check_if_all(seq, 'empty'):
                        direction = self.get_direction(dest, origin)
                        if is_dumb(origin, origin + direction * len(seq)):
                            return []
                        newseq = self.get_range(origin, origin + direction * len(seq))
                        if self.check_if_all(newseq, 'troll'):
                            return capturable
            return []

        def is_valid_move(origin, dest):
            def max_troll_move():
                return {'classic': 1, 'klash': 1, 'kvt': 3}[self.ruleset]

            squares = self.get_range(origin, dest)
            if squares[0] == 'dwarf':
                del squares[0]
                if not self.check_if_all(squares, 'empty'):
                    return False
            elif squares[0] == 'troll':
                del squares[0]
                if len(squares) > max_troll_move():
                    return False
                if not self.check_if_all(squares, 'empty'):
                    return False
            elif squares[0] == 'thudstone':
                if not len(squares) == 2 or not squares[1] == 'empty':
                    return False
                count, count2 = 0, 0
                for i in self.cycle_direction():
                    if self.dwarfs[origin + i]:
                        count += 1
                    if self.dwarfs[dest + i]:
                        count2 += 1
                if count < 2 or count2 < 2:
                    return False
            return True

        move, cap = None, None

        if self.ruleset == 'klash' and is_materializing(origin, dest):
            return (False, False, [origin])

        if is_dumb(origin, dest):
            return (False, False, [])

        if testmoves:
            move = is_valid_move(origin, dest)

        if testcaps:
            if self.ruleset == 'kvt':
                cap = is_valid_cap_kvt(origin, dest)
            else:
                cap = is_valid_cap_normal(origin, dest)

        if self.ruleset == 'kvt' and must_be_jump(origin) and not cap:
            return (False, False, [])

        return (move, bool(cap), cap)

    def get_game_outcome(self):
        """Return the winning side ('dwarf'/'troll'), or None if still playing."""
        def check_rout(token):
            board = {'dwarf': self.dwarfs, 'troll': self.trolls}[token]
            return not board

        def check_mobilized():
            """True if all dwarfs form one connected component."""
            pieces = self.dwarfs.get_bits()
            openset = [next(pieces)]
            closedset = []
            while openset:
                closedset.append(openset[0])
                for i in self.tokens_adjacent(openset[0], 'dwarf'):
                    if i not in closedset:
                        openset.append(i)
                del openset[0]
            return len(set(closedset)) == len(self.dwarfs)

        def check_thudstone_saved():
            """Dwarf KVT win: thudstone reached row 1 between files F and K."""
            goal_squares = list(map(Ply.tuple_to_position, [(6,1),(7,1),(8,1),(9,1),(10,1)]))
            if list(self.thudstone.get_bits())[0] in goal_squares:
                return True

        def check_thudstone_captured():
            """Troll KVT win: thudstone surrounded by 3+ trolls."""
            if len(self.tokens_adjacent(list(self.thudstone.get_bits())[0], 'troll')) >= 3:
                return True

        def klash_win_conditions():
            if (self.turn_to_act() == 'troll'
                    and self.klash_trolls == 6 and check_rout('troll')):
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and check_rout('dwarf'):
                return 'troll'
            elif self.turn_to_act() == 'troll' and check_mobilized():
                return 'dwarf'

        def classic_win_conditions():
            if self.turn_to_act() == 'troll' and check_rout('troll'):
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and check_rout('dwarf'):
                return 'troll'

        def kvt_win_conditions():
            if self.turn_to_act() == 'troll' and check_rout('troll'):
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and check_rout('dwarf'):
                return 'troll'
            elif check_thudstone_saved():
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and check_thudstone_captured():
                return 'troll'

        if self.ruleset == 'classic':
            return classic_win_conditions()
        elif self.ruleset == 'kvt':
            return kvt_win_conditions()
        elif self.ruleset == 'klash':
            return klash_win_conditions()

    def make_set(self, direction, distance, destinations):
        """Convert a set of destination positions into (origin, dest, direction) triples."""
        return [(i - direction * distance, i, direction) for i in destinations]

    def find_moves(self, token):
        """Yield every legal (non-capture) move for every piece of ``token``.

        Uses bitboard shifts to enumerate destinations directly; doesn't
        need to call validate_move per candidate.
        """
        max_dist = {'troll': 1, 'dwarf': 15, 'thudstone': 0}[token]

        for d in self.cycle_direction():
            shift = {
                'troll': copy.deepcopy(self.trolls),
                'dwarf': copy.deepcopy(self.dwarfs),
                'thudstone': copy.deepcopy(self.thudstone),
                }[token]
            for dist in range(1, max_dist + 1):
                if d > 0:
                    shift = (shift >> d) & ~self.occupied_squares() & self.playable
                elif d < 0:
                    shift = (shift << abs(d)) & ~self.occupied_squares() & self.playable
                moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                if not moves:
                    break
                for i in moves:
                    yield Ply(token, i[0], i[1], [])

    def find_caps(self, token):
        """Yield every legal capture for every piece of ``token``.

        Bitboard shifts narrow the candidate set; validate_move is called
        per candidate to apply the full capture rules.
        """
        for d in self.cycle_direction():
            shift = {
                'troll': copy.deepcopy(self.trolls),
                'dwarf': copy.deepcopy(self.dwarfs),
                'thudstone': copy.deepcopy(self.thudstone),
                }[token]
            for dist in range(1, 7):
                if token == 'troll':
                    if d > 0:
                        shift = (shift >> d) & ~self.occupied_squares() & self.playable
                    elif d < 0:
                        shift = (shift << abs(d)) & ~self.occupied_squares() & self.playable
                    moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                    if not moves:
                        break
                    for i in moves:
                        result = self.validate_move(i[0], i[1], False, True)
                        if result[1]:
                            yield Ply(token, i[0], i[1], result[2])
                elif token == 'dwarf':
                    if d > 0:
                        shift = (shift >> d) & self.playable & (~self.occupied_squares() | self.trolls)
                    elif d < 0:
                        shift = (shift << abs(d)) & self.playable & (~self.occupied_squares() | self.trolls)
                    moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                    if not moves:
                        break
                    for i in moves:
                        if self.trolls[i[1]]:
                            result = self.validate_move(i[0], i[1], False, True)
                            if result[1]:
                                yield Ply(token, i[0], i[1], result[2])

    def find_setups(self, token, other_map=None):
        """Yield potential setup-moves (one-move-from-capture) for ``token``.

        Dwarf strategy relies on this minimally, so the dwarf branch
        requires an ``other_map`` Bitboard of target squares of interest.
        """
        def pieces_within_reach(dest, pcs_locked):
            if token == 'troll':
                available = set(self.trolls.get_bits()).difference(pcs_locked)
            elif token == 'dwarf':
                available = set(self.dwarfs.get_bits()).difference(pcs_locked)
            reachable = []
            for i in available:
                if self.validate_move(i, dest, True, False)[0]:
                    reachable.append(i)
            return reachable

        def find_valid_solutions(ply):
            valid_support_plies, support_ready = [], []

            if token == 'troll':
                squares = self.get_range(ply.origin, ply.dest)
                squares.pop(0)
                squares.pop(-1)
                if not self.check_if_all(squares, 'empty'):
                    return []

                direction = self.get_direction(ply.dest, ply.origin)
                iterator = ply.origin
                while self.trolls[iterator]:
                    support_ready.append(iterator)
                    iterator += direction

                deficiency = len(squares) - len(support_ready)
                if deficiency == 1:
                    support_reqd = [support_ready[0] - direction,
                                    support_ready[-1] + direction]
                elif deficiency == 2:
                    support_reqd = [support_ready[0] - direction]
                else:
                    return []

                for i in support_reqd:
                    support_verified = pieces_within_reach(i, support_ready)
                    for p in support_verified:
                        valid_support_plies.append(Ply('troll', p, i, []))
            elif token == 'dwarf':
                squares = self.get_range(ply.origin, ply.dest)
                if len(squares) == 3:
                    direction = self.get_direction(ply.dest, ply.origin)
                    support_reqd = ply.origin + direction
                    support_verified = pieces_within_reach(support_reqd, [ply.origin])
                elif len(squares) == 4:
                    direction = self.get_direction(ply.origin, ply.dest)
                    support_reqd = ply.origin + direction
                    support_verified = pieces_within_reach(support_reqd, [ply.origin])
                else:
                    return []

                for p in support_verified:
                    valid_support_plies.append(Ply('dwarf', p, support_reqd, []))

            return valid_support_plies

        def find_potential_setups():
            for d in self.cycle_direction():
                shift = {
                    'troll': copy.deepcopy(self.trolls),
                    'dwarf': copy.deepcopy(self.dwarfs),
                    'thudstone': copy.deepcopy(self.thudstone),
                    }[token]
                for dist in range(1, 15):
                    if token == 'troll':
                        if d > 0:
                            shift = (shift >> d) & self.playable & (~self.occupied_squares() | self.dwarfs)
                        elif d < 0:
                            shift = (shift << abs(d)) & self.playable & (~self.occupied_squares() | self.dwarfs)
                        moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                        if not moves:
                            break
                        for i in moves:
                            if self.dwarfs[i[1]]:
                                yield Ply('troll', i[0], i[1], [])
                    if token == 'dwarf':
                        if not other_map:
                            return
                        if d > 0:
                            shift = (shift >> d) & self.playable & (~self.occupied_squares() | other_map)
                        elif d < 0:
                            shift = (shift << abs(d)) & self.playable & (~self.occupied_squares() | other_map)
                        moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                        if not moves:
                            break
                        for i in moves:
                            if other_map[i[1]]:
                                yield Ply(token, i[0], i[1], [])

        for i in find_potential_setups():
            for v in find_valid_solutions(i):
                yield v
