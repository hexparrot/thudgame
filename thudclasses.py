"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from array import array
import math
import itertools

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
    BOARD_WIDTH = 17
    
    def __init__(self, add, subtract):
        imported_board = array('B')
        for x in list(str(add)): imported_board.append(int(x))
        
        imported_board2 = array('B')
        for x in list(str(subtract)): imported_board2.append(int(x))
        
        self.influence_map = array('B')
        for x in range(InfluenceMap.BOARD_WIDTH**2): self.influence_map.append(0)
        
        for i,v in enumerate(imported_board):
            if int(v):
                self.hit(i, 6)
        for i,v in enumerate(imported_board2):
            if int(v):
                self.hit(i, -6)

    def __getitem__(self, key):
        return  self.influence_map[key]

    def hit(self, pos, value=6):      
        for i in itertools.product([-3,-2,-1,0,1,2,3], repeat=2):
            try:
                position = (pos + (i[0] * 1) + (i[1] * InfluenceMap.BOARD_WIDTH))
                if position % 17 == 0 or \
                   position % 17 == 16 or \
                   position < 17 or \
                   position > 271:
                    pass
                else:
                    self.influence_map[position] += value // max(abs(i[0]),abs(i[1]),1)
            except:
                pass

    def highest(self, variance_pct=0):
        highest = max(self.influence_map)
        candidates = [] 

        for i,v in enumerate(self.influence_map):
            if v >= highest * (1-variance_pct):
                candidates.append(i)
        return candidates            

    def display(self):
        for i, v in enumerate(self.influence_map):
            if not i % self.BOARD_WIDTH: print()
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

    def __init__(self, token, origin, dest, captured=[]):
        self.token = token
        self.origin = origin
        self.dest = dest
        self.captured = captured
        self.score = -100

    def __str__(self):  
        def make_capstring(captures):
            cap_string = []
            for cap in captures:
                cap_string.append('x' + self.position_to_notation(cap))
            return ''.join(cap_string)      

        return str(self.abbr.get(self.token)) + \
               str(self.position_to_notation(self.origin)) + '-' + \
               str(self.position_to_notation(self.dest)) + \
               make_capstring(self.captured)

    def __eq__(self, other):
        if self.score == other.score:
            return True

    def __lt__(self, other):
        if self.score < other.score:
            return True
    
    def __hash__(self):
        return (self.origin) + (self.dest << 9)
        
    def __bool__(self):
        if self.token and self.origin and self.dest:
            return True
        return False

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

    @staticmethod
    def parse_string(ply_notation):
        """Accepts a string indicating a full move, parses into a ply"""
        import re

        side = {    'd': 'dwarf',
                    'T': 'troll',
                    'R': 'thudstone' }

        REGEX_NOTATION_PLY = r"([T|d|R]) ?([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)"
        compiled_notation = re.compile(REGEX_NOTATION_PLY)
        m = compiled_notation.search(str(ply_notation))
        if m:
            return Ply(side.get(m.group(1)), \
                        Ply.notation_to_position(m.group(2) + m.group(3)), \
                        Ply.notation_to_position(m.group(4) + m.group(5)), \
                        list(map(Ply.notation_to_position, m.group(6).split('x')[1:])))
