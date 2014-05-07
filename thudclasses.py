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
    BOARD_WIDTH = 17
    def __init__(self, positions=[]):
        self.x, self.value = 0, 0

        for i in positions:
            self.value += 1 << (Bitboard.BOARD_WIDTH**2 - i - 1)

    def __str__(self):
        s = bin(self.value)
        if s.startswith('-',0,1):
            s = s.lstrip('-0b').zfill(Bitboard.BOARD_WIDTH**2)
            s = s.replace('1','2').replace('0','1').replace('2','0')
            return s[:-1] + '1'
        return s.lstrip('0b').zfill(Bitboard.BOARD_WIDTH**2)

    def __len__(self):
        return str(self).lstrip('-0b').count('1')
    
    def __getitem__(self, key):
        return str(self)[key]

    def __iter__(self):
        return self

    def __next__(self):
        self.x += 1
        if self.x > Bitboard.BOARD_WIDTH**2:
            self.x = 0
            raise StopIteration
        return self[self.x - 1]

    def __lshift__(self, other):
        new_board = Bitboard()
        new_board.value = self.value << other
        return new_board

    def __rshift__(self, other):
        new_board = Bitboard()
        new_board.value = self.value >> other
        return new_board

    def __and__(self, other):
        new_board = Bitboard()
        new_board.value = self.value & other.value
        return new_board

    def __or__(self, other):
        new_board = Bitboard()
        new_board.value = self.value | other.value
        return new_board

    def __invert__(self):
        new_board = Bitboard.create(self.value)
        new_board.value = ~new_board.value
        return new_board

    def __bool__(self):
        return bool(len(self))

    def get_bits(self):
        for i, v in enumerate(str(self)):
            if int(v):
                yield i

    @staticmethod
    def create(integer):
        new_board = Bitboard()
        new_board.value = integer
        return new_board

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
        for i,v in self.captured:
            caps += (v << ((i+2)*9))
        return (self.origin) + (self.dest << 9) + caps
        
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
        regex_ply_notation = r"([T|d|R])([A-HJ-P])([0-9]+)-([A-HJ-P])([0-9]+)(.*)"
        compiled_notation = re.compile(regex_ply_notation)
        m = compiled_notation.search(str(ply_notation))
        if m:
            return Ply(m.group(1), \
                       Notation(Notation.to_number.get(m.group(2)), int(m.group(3))-1), \
                       Notation(Notation.to_letter.get(m.group(4)), int(m.group(5))-1), \
                       m.group(6).split('x')[1:])











