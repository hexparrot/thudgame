#!/usr/bin/env python3
"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from thud import *
from thudclasses import *
import sys
import re

if __name__ == '__main__':
    ply_list = [l.strip('\n') for l in sys.stdin.readlines()]
    newgame = Gameboard('classic')

    try:
        for move in ply_list:
            p = Ply.parse_string(move)

            if not p:
                if len(newgame.ply_list) == 0:
                    continue
                break

            valid = newgame.validate_move(p.origin, p.dest)
            if valid[0] or valid[1]:
                newgame.apply_ply(p)
                newgame.ply_list.append(p)
            else:
                raise RuntimeError(len(newgame.ply_list), move)

    except RuntimeError as e:
        if sys.argv[1] == 'next_move':
            print('{}:{}'.format(e[0], e[1]))
        elif sys.argv[1] == 'validate':
            print('False')
    else:
        if sys.argv[1] == 'next_move':
            ai_thread = threading.Thread(target=AIEngine.calculate_best_move(newgame, \
                                                                             newgame.turn_to_act(), \
                                                                             0))
            ai_thread.start()
            ai_thread.join()
            print(ai.decision)
        elif sys.argv[1] == 'validate':
            print('True')
    finally:
        exit(0)

