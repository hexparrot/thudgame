"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from thudclasses import *

import copy
import math
import re
import itertools
import random
import sys
import threading
import logging
import sys

ai_log = logging.getLogger('ai_logger')
ai_log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
ai_log.addHandler(handler)

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
        """
        Returns token of allowed player move.
        This is only relevant on classic/klash since KVT
        has additional rules allowing trolls to make multicaptures.
        """
        return len(self.ply_list) % 2 and 'troll' or 'dwarf'

    def display(self, board):
        """Formats the 17x17 string from str(bitboard) to the debug output"""
        for i, v in enumerate(str(board)):
            if not i % self.BOARD_WIDTH: print()
            print(str(v).rjust(2), end='')
    
    def get_default_positions(self, token, ruleset):
        """Returns the starting positions of a given token"""        
        def playable():
            nonlocal ruleset
            pos = []
            
            if ruleset == 'klash': dist_from_center = [0,0,2,3,4,5,6,6,6,6,6,5,4,3,2,0,0]
            else: dist_from_center = [0,2,3,4,5,6,7,7,7,7,7,6,5,4,3,2,0]
            
            for i, v in enumerate(dist_from_center):
                if v:
                    for j in range(-v,v+1):
                        pos.append((i,(self.BOARD_WIDTH//2)+j))
            return pos

        def thudstone():
            return [(8,8)]

        def troll():
            nonlocal ruleset

            return {
                'classic': [(7,7),(8,7),(9,7),
                            (7,8),      (9,8),
                            (7,9),(8,9),(9,9)],
                'kvt': [(6,2),(8,2),(10,2),
                        (5,3),(6,3),(8,3),(10,3),(11,3)],
                'klash': []
                }[ruleset]

        def dwarf():
            nonlocal ruleset

            return {
                'classic': [(6,1), (7,1), (9,1), (10,1),
                            (5,2), (11,2),(4,3), (12,3),
                            (3,4), (13,4),(2,5), (14,5),

                            (1,6), (15,6),(1,7), (15,7),
                            (1,9), (15,9),(1,10), (15,10),

                            (2,11), (14,11),(3,12), (13,12),
                            (4,13), (12,13),(5,14), (11,14),
                            (6,15), (7,15), (9,15), (10,15) ],
                'kvt': [(8, 9), (1, 10), (15, 10), \
                        (2,11), (14,11), \
                        (3,12), (13,12), \
                        (4,13), (12,13), \
                        (5,14), (11,14), \
                        (6,15), (7 ,15), (8,15), (9,15), (10,15) ],
                'klash':[(6, 2), (7, 2), (9, 2), (10, 2), \
                         (5, 3), (11,3), \
                         (3, 5), (13,5), \
                         (2, 6), (14,6), \
                         (2, 7), (14,7), \
                         (2, 9), (14,9), \
                         (2,10), (14,10),\
                         (3,11), (13,11),\
                         (5,13), (11,13),\
                         (6,14), (10,14),\
                         (7,14), ( 9,14) ]
                }[ruleset]

        notations = {
            'playable': playable(),
            'thudstone': thudstone(),
            'troll': troll(),
            'dwarf': dwarf()
            }[token]

        return map(Ply.tuple_to_position, notations)

    def get_default_board(self, board_type, ruleset='classic'):
        """
        Returns a bitboard with all the positions for a token/ruleset.
        This is used to increase readability, since get_default_positions
        only returns positions, not a board.
        """
        return Bitboard(self.get_default_positions(board_type, ruleset))

    def occupied_squares(self):
        """
        Shortcut bitboard of all squares currently occupied
        """
        return self.dwarfs | self.trolls | self.thudstone

    def token_at(self, position):
        """
        Checks all bitboards to see which piece resides on the square.
        """
        if int(self.trolls[position]):
            return 'troll'
        elif int(self.dwarfs[position]):
            return 'dwarf'
        elif int(self.thudstone[position]):
            return 'thudstone'
        elif int(self.playable[position]):
            return 'empty'            

    def add_troll(self, pos):
        """
        Klash-use only.  Adds a troll via bitboard, but also increments
        Klash materialized max count.
        """
        self.trolls |= Bitboard([pos])
        self.klash_trolls += 1
                            
    def apply_ply(self, ply):
        """
        Processes a ply through each bitboard.
        """
        if ply.token == 'troll':
            self.trolls = self.trolls & ~Bitboard([ply.origin]) | Bitboard([ply.dest])
            self.dwarfs = self.dwarfs & ~Bitboard(ply.captured)
        elif ply.token == 'dwarf':
            self.dwarfs = self.dwarfs & ~Bitboard([ply.origin]) | Bitboard([ply.dest])
            self.trolls = self.trolls & ~Bitboard(ply.captured)
        elif ply.token == 'thudstone':
            self.thudstone = self.thudstone & ~Bitboard([ply.origin]) | Bitboard([ply.dest])

    def cycle_direction(self):
        """
        A generator yielding all 8 outward directions.
        """
        for i in [-self.BOARD_WIDTH-1, -self.BOARD_WIDTH, -self.BOARD_WIDTH+1,
                  self.BOARD_WIDTH-1, self.BOARD_WIDTH, self.BOARD_WIDTH+1,
                  -1, 1]:
            yield i

    def get_delta(self, origin, dest):
        """
        Determines the general direction of two locations.
        Works on all input but does not guarantee precision.
        Will return (-1,0,1) x (-1,0,1).
        """
        delta_file = (dest[0] > origin[0]) - (dest[0] < origin[0])
        delta_rank = (dest[1] > origin[1]) - (dest[1] < origin[1])
        return (delta_file, delta_rank)

    def delta_to_direction(self, delta):
        """
        Translate a general direction (get_delta) into a usable direction
        """
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
        """
        Readability function to take two locations amd return a discrete direction,
        with limited accuracy.
        """
        delta = self.get_delta(Ply.position_to_tuple(origin), Ply.position_to_tuple(dest)) 
        return self.delta_to_direction(delta)

    def check_if_all(self, seq, token):
        """
        Function returns true if all members in seq are of token type.
        """
        for i in filter(lambda x: x != token, seq):
            return False
        return True

    def get_range(self, origin, dest):
        """
        Returns a list of tokens from and including origin to dest.
        """
        direction = self.get_direction(origin, dest)
        pc_range = []
        for i in range(origin, dest + direction, direction):
            pc_range.append(self.token_at(i))
        return pc_range

    def tokens_adjacent(self, position, token):
        """
        Returns a list of a given token adjacent to a position.
        """
        capturable = []
        for d in filter(lambda x: self.token_at(position+x) == token, \
                        self.cycle_direction()):
            capturable.append(position+d)
        return capturable

    def validate_move(self, origin, dest, testmoves=True, testcaps=True):
        """
        Master fucntion--receives two locations and determines validity of move/capture.
        Function will check origin piece and automatically use applicable logic
        for movement and captures.
        """
        def is_materializing(origin, dest):
            """
            If true, the move attempted is to materialize a troll in KLASH
            """
            if origin == dest and \
               (len(self.ply_list) % 2 and 'troll') and \
               self.token_at(origin) == 'empty' and \
               origin in self.get_default_positions('troll', 'classic'):
                return True

        def is_dumb(origin, dest):
            """
            If true, the move is invalid under all circumstance and games.
            Exception is is_materializing which must be called prior to this.
            """
            try:
                if not Bitboard([origin]) & self.playable:
                    return True
                elif not Bitboard([dest]) & self.playable:
                    return True
                elif origin == dest:
                    return True
                else:
                    t_origin, t_dest = Ply.position_to_tuple(origin), Ply.position_to_tuple(dest)
                    if t_origin[0] - t_dest[0] and t_origin[1] - t_dest[1]:
                        if abs(t_origin[0] - t_dest[0]) != abs(t_origin[1] - t_dest[1]):
                            return True
            except:
                return True

        def must_be_jump(position):
            """
            In KVT, if trolls successfully capture,
            trolls may only move again to capture or end turn.
            """
            if self.ply_list and \
               self.ply_list[-1].token == 'troll' and \
               self.ply_list[-1].captured and \
               int(self.trolls[position]):
                return True

        def is_valid_cap_kvt(origin, dest):
            """
            Checks if a capture is valid in KVT
            """
            capturable = []
            if int(self.dwarfs[origin]):
                for i in self.tokens_adjacent(dest, 'troll'):
                    direction = self.get_direction(dest, i)
                    seq = self.get_range(dest, dest + direction + direction)
                    if seq == ['empty', 'troll', 'dwarf']:
                        capturable.append(dest + direction)
                return capturable
            elif int(self.trolls[origin]):
                if self.get_range(origin, dest) == ['troll', 'dwarf', 'empty']:
                    return [origin + self.get_direction(origin, dest)]
            return []

        def is_valid_cap_normal(origin, dest):
            """
            Checks if a capture is valid in normal/klash
            """
            verified, capturable = [], []
            
            if int(self.dwarfs[origin]):
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
            elif int(self.trolls[origin]):
                seq = self.get_range(origin, dest)
                if seq.pop(-1) == 'empty' and seq.pop(0) == 'troll':
                    capturable = self.tokens_adjacent(dest, 'dwarf')
                    if not capturable: return []
                    elif not seq: return capturable
                    elif self.check_if_all(seq, 'empty'):
                        direction = self.get_direction(dest, origin)
                        if is_dumb(origin, origin + direction * len(seq)):
                            return []
                        newseq = self.get_range(origin, origin + direction * len(seq))
                        if self.check_if_all(newseq, 'troll'):
                            return capturable
            return []

        def is_valid_move(origin, dest):
            """Performs all logic for all rulesets about movement of pieces"""
            def max_troll_move():
                """Returns the number of moves a troll may make in current ruleset"""
                return {
                    'classic': 1,
                    'klash': 1,
                    'kvt': 3
                    }[self.ruleset]

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
                    if self.dwarfs[origin+i]:
                        count += 1 
                    if self.dwarfs[dest+i]:
                        count2 += 1
                if count < 2 or count2 < 2:
                    return False
            return True

        move, cap = None, None
        
        if self.ruleset == 'klash' and \
           is_materializing(origin, dest):
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

        if self.ruleset == 'kvt' and \
             must_be_jump(origin) and \
             not cap:
            return (False, False, [])

        return (move, bool(cap), cap)

    def get_game_outcome(self):
        """Returns a string of the winning agent"""
        def check_rout(token):
            board = {
                'dwarf': self.dwarfs,
                'troll': self.trolls
                }[token]
            return not board

        def check_mobilized():
            """Iterate through network of dwarfs to see if all are physically connected"""
            def unique(pos_list):  
                checked = []
                for i in filter(lambda x: x not in checked, pos_list):
                    checked.append(i)
                return checked

            pieces = self.dwarfs.get_bits()
            openset = [next(pieces)]
            closedset = []

            while len(openset):
                closedset.append(openset[0])
                for i in self.tokens_adjacent(openset[0], 'dwarf'):
                    if i not in closedset:
                        openset.append(i)
                del openset[0]

            if len(unique(closedset)) == len(self.dwarfs):
                return True

        def check_thudstone_saved():
            """Dwarf win if thudstone successfuly moved to top of board"""
            goal_squares = list(map(Ply.tuple_to_position, [(6,1),(7,1),(8,1),(9,1),(10,1)]))
            if list(self.thudstone.get_bits())[0] in goal_squares:
                return True

        def check_thudstone_captured():
            """Troll win if thudstone surrounded by 3 trolls"""
            if len(self.tokens_adjacent(list(self.thudstone.get_bits())[0], 'troll')) >= 3:
                return True

        def klash_win_conditions():
            if self.turn_to_act() == 'troll' and \
               self.klash_trolls == 6 and \
               check_rout('troll'):
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and \
               check_rout('dwarf'):
                return 'troll'
            elif self.turn_to_act() == 'troll' and \
               check_mobilized():
                return 'dwarf'

        def classic_win_conditions():
            if self.turn_to_act() == 'troll' and \
               check_rout('troll'):
                return 'dwarf'        
            elif self.turn_to_act() == 'dwarf' and \
               check_rout('dwarf'):
                return 'troll'

        def kvt_win_conditions():
            if self.turn_to_act() == 'troll' and \
               check_rout('troll'):
                return 'dwarf'        
            elif self.turn_to_act() == 'dwarf' and \
               check_rout('dwarf'):
                return 'troll'
            elif check_thudstone_saved():
                return 'dwarf'
            elif self.turn_to_act() == 'dwarf' and \
                 check_thudstone_captured():
                return 'troll'

        if self.ruleset == 'classic':
            return classic_win_conditions()
        elif self.ruleset == 'kvt':
            return kvt_win_conditions()
        elif self.ruleset == 'klash':
            return klash_win_conditions()

    def make_set(self, direction, distance, destinations):
        """Converts bitboard-data points into usable ply-pairs"""
        pairs = []
        for i in destinations:
            #origin, destination, direction
            pairs.append((i-(direction*distance), i, direction))
        return pairs
    
    def find_moves(self, token):
        """
        Yields all possible moves for ALL pieces of a token.
        Bitboards can hold all the logic necessary that validate_move
        is no neccessary.
        """
        def max_movement():
            nonlocal token
            return {
                'troll': 1,
                'dwarf': 15,
                'thudstone': 0
                }[token]
        
        all_moves = []
        max_dist = max_movement()

        for d in self.cycle_direction():
            shift = {
                'troll': copy.deepcopy(self.trolls),
                'dwarf': copy.deepcopy(self.dwarfs),
                'thudstone': copy.deepcopy(self.thudstone),
                }[token]
            for dist in range(1, max_dist+1):
                if d > 0:
                    shift = (shift >> d) & ~self.occupied_squares() & self.playable
                elif d < 0:
                    shift = (shift << abs(d)) & ~self.occupied_squares() & self.playable
                moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                if not moves: break
                for i in moves:
                    yield Ply(token, i[0], i[1], [])

    def find_caps(self, token):
        """
        Yields all possible captures for ALL pieces of a token.
        Due to the nature of capturing, this function also executes validate_move
        to remove bitboard positives that are illegal.
        """
        all_moves = []

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
                    if not moves: break
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
                    if not moves: break
                    for i in moves:
                        if int(self.trolls[i[1]]):
                            result = self.validate_move(i[0], i[1], False, True)
                            if result[1]:
                                yield Ply(token, i[0], i[1], result[2])

    def find_setups(self, token, other_map=None):
        """
        Yields all possible setups for ALL pieces of a token.
        Dwarf strategy minimally relies on this, and therefore it has not been implemented.
        """        
        def pieces_within_reach(dest, pcs_locked):
            """
            Determines if pieces are availble to move into deficit areas
            that are not already relied on for the capture
            """
            nonlocal token

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
            """
            Checks each potential setup and determines if piece
            may be added to front or back of line to be valid
            """
            nonlocal token
            valid_support_plies, support_ready = [], []

            if token == 'troll':
                squares = self.get_range(ply.origin, ply.dest)
                squares.pop(0)
                squares.pop(-1)
                if not self.check_if_all(squares, 'empty'):
                    return []

                direction = self.get_direction(ply.dest, ply.origin)
                iterator = ply.origin
                while int(self.trolls[iterator]):
                    support_ready.append(iterator)
                    iterator += direction

                deficiency = len(squares) - len(support_ready)
                #if line is short one, support required is ONE of the two -- back or front
                if deficiency == 1:
                    support_reqd = [support_ready[0] - direction, support_ready[-1] + direction]
                #if line is short two, support required MUST be front, else requires too many moves to care
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
            """
            Locate pieces that have potential attacks in each direction.
            Eliminates lines that require more than 1 pc to complete.
            """
            nonlocal token
            nonlocal other_map

            for d in self.cycle_direction():
                shift = {
                    'troll': copy.deepcopy(self.trolls),
                    'dwarf': copy.deepcopy(self.dwarfs),
                    'thudstone': copy.deepcopy(self.thudstone),
                    }[token]
                for dist in range(1, 15):
                    if token == 'troll':
                        if d > 0:
                            shift = Bitboard.create(shift.value >> d) & self.playable & (~self.occupied_squares() | self.dwarfs)
                        elif d < 0:
                            shift = Bitboard.create(shift.value << abs(d)) & self.playable & (~self.occupied_squares() | self.dwarfs) 
                        moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                        if not moves: break
                        for i in moves:
                            if int(self.dwarfs[i[1]]):
                                yield Ply('troll', i[0], i[1], [])
                    if token == 'dwarf':
                        if not other_map: return
                        if d > 0:
                            shift = (shift >> d) & self.playable & (~self.occupied_squares() | other_map)
                        elif d < 0:
                            shift = (shift << abs(d)) & self.playable & (~self.occupied_squares() | other_map)  
                        moves = self.make_set(d, dist, frozenset(shift.get_bits()))
                        if not moves: break
                        for i in moves:
                            if int(other_map[i[1]]):
                                yield Ply(token, i[0], i[1], [])

        for i in find_potential_setups():
            for v in find_valid_solutions(i):
                yield v
        

class AIEngine(threading.Thread):
    def __init__(self, board):
        self.board = copy.deepcopy(board)
        self.moves = []
        self.threats = []
        self.setups = []

    def apply(self, ply_list):
        """Apply a ply to a board"""
        for p in ply_list:
            self.board.apply_ply(p)
            self.board.ply_list.append(p)

    def score(self, token):
        """Scoring function to determine favorability of result"""
        if token == 'troll':
            score = len(self.board.trolls) * 4 - len(self.board.dwarfs)
            score -= self.filter_threatened_pieces('troll') * 4
        else:
            score = len(self.board.dwarfs) - len(self.board.trolls) * 4
            score -= self.filter_threatened_pieces('dwarf')
            
        return score

    def filter_adjacent_threats(self, token):
        """
        Identifies enemies that are adjacent to eachother and finds all
        captures to eliminate this threat.  This logic *should* be called
        first, e.g., trolls will lose 4 pts immediately if unattended
        """
        def unique(positions):
            """Removes duplicates in list"""
            checked = []
            for i in filter(lambda x: x not in checked, positions):
                checked.append(i)
            return checked
        
        adjacent_threats, solutions = [], []
        if token == 'troll':
            for t in self.board.trolls.get_bits():
                adjacent_threats.extend(self.board.tokens_adjacent(t, 'dwarf'))
            adjacent_threats = unique(adjacent_threats)
        elif token == 'dwarf':
            pass

        for j in adjacent_threats:
            for t in self.threats:
                if j in t.captured:
                    solutions.append(t)
        return solutions

    def filter_capture_destinations(self, ply_list):
        def unique(pos_list):  
            checked = []
            for i in filter(lambda x: x not in checked, pos_list):
                checked.append(i)
            return checked

        dest_positions = []
        for p in ply_list:
            dest_positions.append(p.dest)

        return unique(dest_positions)

    def find_line_blocks(self):
        """
        Checks if a dwarf can be placed at the front of a troll line
        to effectively stop a shove.  Considers adjacent blocking square
        as well as 1-off, which helps reduce the chances of a non-line
        troll from eliminating the dwarf without interrupting the line.
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
        """Counts the number of pieces that can be captured next turn hypothetically."""
        def is_threatened(pos):
            """Cycles opposing token to verify capture is possible of given pos."""
            if self.board.trolls[pos]:
                for i in self.board.dwarfs.get_bits():
                    if self.board.validate_move(i, pos, False, True)[1]:
                        return True
            elif self.board.dwarfs[pos]:
                for i in self.board.trolls.get_bits():
                    direction = self.get_direction(i, pos)
                    if self.board.validate_move(i, i + direction, False, True)[1]:
                        return True
                    
        pieces = {
            'troll': self.board.trolls,
            'dwarf': self.board.dwarfs
            }[friendly_token]
        count = 0

        for i in pieces.get_bits():
            if is_threatened(i):
                count += 1
        return count            

    def nonoptimal_troll_moves(self):
        """Makes a move in a semi-educated fashion."""
        def alternate_direction(general_direction):
            """
            If location is occupied, choose a direction
            with at least one kept vector.
            This may never be execute, as it can occur
            ONLY if a troll cannot move due to thudstone.
            """
            candidates = []
            significant_vector_f = general_direction[0] or 0
            significant_vector_r = general_direction[1] or 0

            if significant_vector_f and significant_vector_r:
                candidates.append((significant_vector_f,0))
                candidates.append((0,significant_vector_r))
            elif significant_vector_f:
                candidates.append((significant_vector_f,-1))
                candidates.append((significant_vector_f,1))                
            elif significant_vector_r:
                candidates.append((-1,significant_vector_r))
                candidates.append((1,significant_vector_r))
            return random.choice(candidates)
        
        lowest = 100

        for t in self.board.trolls.get_bits():
            for d in self.board.dwarfs.get_bits():
                hypotenuse = Ply.calc_pythagoras(t, d)
                if hypotenuse < lowest:
                    lowest = hypotenuse
                    candidates = []                    
                if hypotenuse == lowest:
                    delta = self.board.get_delta(Ply.position_to_tuple(t), \
                                                 Ply.position_to_tuple(d))
                    direction = self.board.delta_to_direction(delta)
                    while self.board.token_at(t + direction) != 'empty':
                        delta = alternate_direction(delta)
                        direction = self.board.delta_to_direction(delta)
                    candidates.append(Ply('troll', t, t + direction, []))
        return candidates

    def filter_dwarfs_can_reach(self, dense_spots):
        """
        Given a set of desirable locations for dwarfs,
        find which plies will satisfy this move
        """
        for d in dense_spots:
            for m in self.moves:
                if d == m.dest:
                    yield m

    def filter_farthest_dwarfs(self, ply_list, variance=.4):
        """
        Filter out dwarfs that are near, and keep only those that are far,
        so that flocking does not consist of dwarfs moving 1/2 squares only.
        """
        farthest = 0
        candidates = []

        for i in ply_list:
            farthest = max(farthest, Ply.calc_pythagoras(i.origin, i.dest))

        if farthest <= math.sqrt(2):
            return []

        for i in ply_list:
            if Ply.calc_pythagoras(i.origin,i.dest) >= farthest * (1-variance):
                candidates.append(i)
        return candidates        

    def filter_best(self, token, candidates, variance_pct=0):
        """
        Goes through a list of plies and determine which results in best score
        """
        for p in candidates:
            scratch = AIEngine(self.board)
            scratch.apply((p,))
            p.score = scratch.score(token)
        candidates = sorted(candidates, key=lambda v: v.score, reverse=True)

        top = list(filter(lambda p: p.score >= candidates[0].score * (1-variance_pct), candidates))   
        if top:
            return random.choice(top)
        return Ply(None,None,None,None)

    @staticmethod
    def predict_future(board, firstply, lookahead, token):
        """
        Takes a ply and goes x moves ahead, returning the score.
        """
        global ai
        b = AIEngine(board)
        b.apply((firstply,))
        for i in range(1, lookahead+1):
            try:
                AIEngine.calculate_best_move(b.board, b.board.turn_to_act(), 0)
            except NoMoveException:
                break
            b.apply((ai.decision,))
        return b.score(token)

    @staticmethod
    def select_best_future(board, plies, lookahead, token):
        """
        Takes a list of plies and determines out the most favorable
        """

        best_score = -101
        best_ply = None

        for i, ply in enumerate(plies):
            score = AIEngine.predict_future(board, \
                                            ply, \
                                            lookahead, \
                                            token)
            if score > best_score:
                best_score = score
                best_ply = ply
        return best_ply

    @staticmethod
    def calculate_best_move(board, token, lookahead=0):
        """
        Takes a board position and calculates the best move for a token.
        Can also be used to lookahead x moves in conjunction with predict_future.
        """
        def dest_more_dense(imap, ply):
            if imap[ply.dest] > imap[ply.origin]:
                return True
            return False
        
        global ai
        best_cap, best_setup, best_move = None, None, None
        
        b = AIEngine(board)
        
        if not len(b.board.dwarfs): raise NoMoveException('dwarf')
        elif not len(b.board.trolls): raise NoMoveException('troll')
  
        if token == 'troll':
            ai_log.info('TROLL')
            ai_log.info('turn: %d', len(b.board.ply_list) / 2)
            b.threats = list(b.board.find_caps(token))
            b.setups = list(b.board.find_setups(token))

            immediate_threats = b.filter_adjacent_threats(token)
            if immediate_threats:
                ai.decision = b.filter_best(token, immediate_threats)
                ai_log.info('save %i %s', ai.decision.score, ai.decision or 'x')
            else:
                tsb = AIEngine.select_best_future(b.board, itertools.chain(b.threats, b.setups), 0, token)
 
                if tsb:
                    ai.decision = tsb
                else:
                    ai.decision = b.filter_best(token, b.nonoptimal_troll_moves())

            ai_log.info('# threats: %i', len(b.threats))
            ai_log.debug('%s', ', '.join(str(s) for s in b.threats))
            ai_log.info('# setups: %i', len(b.setups))
            ai_log.debug('%s', ', '.join(str(s) for s in b.setups))
            ai_log.info('  T: %i d: %i\n', len(b.board.trolls) * 4, len(b.board.dwarfs))
        elif token == 'dwarf':
            ai_log.info('DWARF')
            ai_log.info('turn: %d', len(b.board.ply_list) / 2)

            b.threats = list(b.board.find_caps(token))

            ai.decision = b.filter_best(token, b.threats)
            ai_log.info('best cap %i %s', ai.decision.score, ai.decision or 'x')
            
            if not ai.decision:
                troll_cd = b.filter_capture_destinations(list(b.board.find_caps('troll')))
                b.setups = list(b.board.find_setups(token, Bitboard(troll_cd)))
                b.moves = list(b.board.find_moves(token))
                b.blocks = list(b.find_line_blocks())
                best_setup = b.filter_best(token, b.filter_farthest_dwarfs(b.setups))

                tsb = AIEngine.select_best_future(b.board, \
                                                  itertools.chain(b.threats, b.setups, b.blocks), \
                                                  lookahead, \
                                                  token)

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
                    ai.decision = AIEngine.select_best_future(b.board, \
                                                              [tsb, best_move], \
                                                              lookahead, \
                                                              token)
                elif best_move:
                    ai.decision = best_move
                else:
                    ai.decision = next(b.board.find_moves('dwarf'))
                
            ai_log.info('# threats: %i', len(list(b.threats)))
            ai_log.debug('%s', ', '.join(str(s) for s in b.threats))
            ai_log.info('# setups: %i', len(b.setups))
            ai_log.debug('%s', ', '.join(str(s) for s in b.setups))
            ai_log.info('# moves: %i', len(b.moves))
            #ai_log.debug('%s', ', '.join(str(s) for s in b.moves))
            ai_log.info('  T: %i d: %i\n', len(b.board.trolls) * 4, len(b.board.dwarfs))
        if not ai.decision:
            raise NoMoveException(token)

ai = threading.local()
