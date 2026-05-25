"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

import itertools
import math
import re

class NoMoveException(Exception):
    '''A user-defined exception class.'''
    def __init__(self, token):
        Exception.__init__(self)
        self.token = token

class MCTSNode:
    def __init__(self, game_state, parent=None):
        self.game_state = game_state
        self.parent = parent
        self.children = []
        self.visits = 0
        self.value = 0

    def __repr__(self):
        return f"MCTSNode(visits={self.visits}, value={self.value})"

    def add_child(self, child_node):
        self.children.append(child_node)

    def update_value(self, new_value):
        self.value += new_value
        self.visits += 1

    def average_value(self):
        if self.visits == 0:
            return 0
        return self.value / self.visits


class InfluenceMap:
    """A 17x17 grid of signed integer "influence" scores.

    Constructed from two Bitboards: ``add`` (friendly pieces, +6 around each)
    and ``subtract`` (enemy pieces, -6 around each). Influence falls off
    linearly with Chebyshev distance, out to a 7x7 footprint per piece.

    Used by AIEngine.calculate_best_move to find dense friendly clusters.
    """

    BOARD_WIDTH = 17

    def __init__(self, add, subtract):
        # Plain list, not array('B'): the prior `array('B')` is unsigned and
        # raised OverflowError as soon as a negative value was added — the
        # error was then silently dropped by the bare `except: pass` in
        # hit(), so subtractive influence from enemy pieces was effectively
        # ignored.
        self.influence_map = [0] * (InfluenceMap.BOARD_WIDTH ** 2)

        add_str = str(add)
        sub_str = str(subtract)
        for i, c in enumerate(add_str):
            if c == '1':
                self.hit(i, 6)
        for i, c in enumerate(sub_str):
            if c == '1':
                self.hit(i, -6)

    def __getitem__(self, key):
        return self.influence_map[key]

    def hit(self, pos, value=6):
        """Add a falloff "splash" of ``value`` centered at ``pos``."""
        for di, dj in itertools.product([-3,-2,-1,0,1,2,3], repeat=2):
            position = pos + di + dj * InfluenceMap.BOARD_WIDTH
            # Skip non-playable edge columns/rows (the 17x17 grid frames a
            # 15x15 playable area; columns 0/16 and rows 0/16 are off-board).
            if (position < 17 or position > 271
                or position % 17 == 0 or position % 17 == 16):
                continue
            self.influence_map[position] += value // max(abs(di), abs(dj), 1)

    def highest(self, variance_pct=0):
        """Return positions whose influence is within ``variance_pct`` of the max."""
        top = max(self.influence_map)
        if top <= 0:
            return []
        threshold = top * (1 - variance_pct)
        return [i for i, v in enumerate(self.influence_map) if v >= threshold]

    def display(self):
        for i, v in enumerate(self.influence_map):
            if not i % self.BOARD_WIDTH:
                print()
            print(str(v).rjust(3), end='')
            

class Bitboard:
    """Fixed-width 289-bit mask over a 17x17 board.

    Bit/position convention: a board position ``p`` (0..288) corresponds to
    bit ``N - 1 - p`` of ``value``. Position 0 is the most-significant bit;
    position 288 is the least-significant bit. ``str(bb)`` is therefore a
    289-character binary string in position order (leftmost char = position 0),
    which is the form ``InfluenceMap`` and ``Gameboard.display`` rely on.

    All operations are width-safe: shifts and ``~`` mask back to the 289-bit
    field so values never go negative or grow beyond the board.
    """

    BOARD_WIDTH = 17
    N = BOARD_WIDTH * BOARD_WIDTH
    MASK = (1 << N) - 1

    __slots__ = ('value',)

    def __init__(self, positions=None):
        self.value = 0
        if positions:
            for p in positions:
                self.value |= 1 << (Bitboard.N - 1 - p)

    def __str__(self):
        return format(self.value & Bitboard.MASK, '0{}b'.format(Bitboard.N))

    def __repr__(self):
        return 'Bitboard.create({})'.format(self.value & Bitboard.MASK)

    def __len__(self):
        return (self.value & Bitboard.MASK).bit_count()

    def __getitem__(self, key):
        if isinstance(key, slice):
            return str(self)[key]
        return (self.value >> (Bitboard.N - 1 - key)) & 1

    def __iter__(self):
        v = self.value & Bitboard.MASK
        for i in range(Bitboard.N):
            yield (v >> (Bitboard.N - 1 - i)) & 1

    def __lshift__(self, other):
        return Bitboard.create((self.value << other) & Bitboard.MASK)

    def __rshift__(self, other):
        return Bitboard.create(self.value >> other)

    def __and__(self, other):
        return Bitboard.create(self.value & other.value)

    def __or__(self, other):
        return Bitboard.create(self.value | other.value)

    def __invert__(self):
        return Bitboard.create((~self.value) & Bitboard.MASK)

    def __bool__(self):
        return bool(self.value & Bitboard.MASK)

    def __eq__(self, other):
        if not isinstance(other, Bitboard):
            return NotImplemented
        return (self.value & Bitboard.MASK) == (other.value & Bitboard.MASK)

    def __hash__(self):
        return hash(self.value & Bitboard.MASK)

    def get_bits(self):
        """Yield positions (0..N-1) of set bits, in ascending order."""
        v = self.value & Bitboard.MASK
        for i in range(Bitboard.N):
            if v & (1 << (Bitboard.N - 1 - i)):
                yield i

    @staticmethod
    def create(integer):
        """Build a Bitboard from a raw integer, masked to the 289-bit field."""
        b = Bitboard()
        b.value = integer & Bitboard.MASK
        return b

class Ply:
    """Implements game-notation fragments"""

    abbr = { 'dwarf': 'd', 'd': 'd',
             'troll': 'T', 'T': 'T',
             'thudstone': 'R', 'R': 'R' }
    
    to_letter = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E',
                 6: 'F', 7: 'G', 8: 'H', 9: 'J', 10:'K',
                 11:'L', 12:'M', 13:'N', 14:'O', 15:'P' }

    to_number = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5,
                 'F': 6, 'G': 7, 'H': 8, 'J': 9, 'K': 10,
                 'L': 11,'M': 12,'N': 13,'O': 14,'P': 15 } 

    def __init__(self, token, origin, dest, captured=None):
        self.token = token
        self.origin = origin
        self.dest = dest
        self.captured = list(captured) if captured else []
        self.score = -100

    def _key(self):
        """Structural-equality key: (token, origin, dest, captured)."""
        return (self.token, self.origin, self.dest, tuple(sorted(self.captured)))

    def __str__(self):
        cap_string = ''.join('x' + self.position_to_notation(cap)
                             for cap in self.captured)
        return (str(self.abbr.get(self.token))
                + str(self.position_to_notation(self.origin)) + '-'
                + str(self.position_to_notation(self.dest))
                + cap_string)

    def __repr__(self):
        return "Ply({!r}, {!r}, {!r}, {!r})".format(
            self.token, self.origin, self.dest, self.captured)

    def __eq__(self, other):
        # Was previously a score comparison that returned True or None
        # (no explicit False branch) — collapsing distinct moves with the
        # same score into one set entry. Score-based ordering is handled
        # by callers via `key=lambda p: p.score`.
        if not isinstance(other, Ply):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __lt__(self, other):
        # Sortable by score (lower = worse for the current side). Callers
        # generally pass an explicit `key=`, but keep this for the
        # natural-sort case. Returns a real bool, not None.
        if not isinstance(other, Ply):
            return NotImplemented
        return self.score < other.score

    def __bool__(self):
        # Was `if token and origin and dest`, which returned False if either
        # position was the integer 0. Position 0 is off the playable board
        # in every current ruleset, but the predicate is still wrong.
        return (self.token is not None
                and self.origin is not None
                and self.dest is not None)

    @staticmethod
    def position_to_tuple(position):
        rank = position // 17
        file = position - (rank * 17)
        return (file, rank)

    @staticmethod
    def position_to_notation(position):
        conv = Ply.position_to_tuple(position)
        file = Ply.to_letter.get(int(conv[0]))
        rank = str(int(conv[1]))
        return file + rank

    @staticmethod
    def notation_to_position(notation):
        file = Ply.to_number.get(notation[0])
        return file + int(notation[1:]) * 17

    @staticmethod
    def tuple_to_position(notation):
        return notation[1] * 17 + notation[0]

    @staticmethod
    def calc_pythagoras(a_pos, b_pos):
        a = Ply.position_to_tuple(a_pos)
        b = Ply.position_to_tuple(b_pos)
        return math.sqrt(pow(a[0] - b[0],2) + pow(a[1] - b[1],2))

    _SIDE_FROM_ABBR = {'d': 'dwarf', 'T': 'troll', 'R': 'thudstone'}
    _PLY_NOTATION_RE = re.compile(
        r"([TdR]) ?([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)"
    )

    @staticmethod
    def parse_string(ply_notation):
        """Parse one ply of game notation (e.g. 'dF1-G2', 'TG7-F7xE7').

        Returns ``None`` if the string does not match the ply grammar.
        """
        m = Ply._PLY_NOTATION_RE.search(str(ply_notation))
        if not m:
            return None
        captures = [Ply.notation_to_position(c) for c in m.group(6).split('x')[1:]]
        return Ply(
            Ply._SIDE_FROM_ABBR.get(m.group(1)),
            Ply.notation_to_position(m.group(2) + m.group(3)),
            Ply.notation_to_position(m.group(4) + m.group(5)),
            captures,
        )
