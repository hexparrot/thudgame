"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from thudclasses import *

import copy
import tkinter
import math
import re
import itertools
import random
import sys
import threading

class RepeatTimer(threading.Thread):
    """
    This borrowed class repeats at 1 second intervals to see if it is a
    computer's turn to act on behalf of the troll/dwarf.
    
    # Copyright (c) 2009 Geoffrey Foster
    # http://g-off.net/software/a-python-repeatable-threadingtimer-class
    """
    def __init__(self, interval, function, iterations=0, args=[], kwargs={}):
        threading.Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.iterations = iterations
        self.args = args
        self.kwargs = kwargs
        self.finished = threading.Event()
 
    def run(self):
        count = 0
        while not self.finished.is_set() and (self.iterations <= 0 or count < self.iterations):
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                self.function(*self.args, **self.kwargs)
                count += 1
 
    def cancel(self):
        self.finished.set()

class DesktopGUI(tkinter.Frame):
    """Implements the main desktop GUI"""
    def __init__(self, master):
        master.title('Thud')

        self.sprites = {}
        self.sprite_lifted = False
        self.review_mode = False
        self.selection_mode = 'false'
        self.selected_pieces = []
        self.displayed_ply = 0
        self.delay_ai = False

        self.compulsory_capturing = tkinter.BooleanVar()
        self.allow_illegal_play = tkinter.BooleanVar()
        self.cpu_troll = tkinter.BooleanVar()
        self.cpu_dwarf = tkinter.BooleanVar()
        self.alt_iconset = tkinter.BooleanVar()
        self.lookahead_count = 3

        self.draw_ui(master)
        self.user_notice.set("")

        self.compulsory_capturing.set(True)
        self.allow_illegal_play.set(False)
        self.alt_iconset.set(False)

    def draw_ui(self, master):
        """Loads all the images and widgets for the UI"""
        BOARD_SIZE = 600
        self.square_size = int(BOARD_SIZE / 15)

        self.image_board = tkinter.PhotoImage(file='tb.gif')
        self.image_troll = tkinter.PhotoImage(file='rook.gif')
        self.image_dwarf = tkinter.PhotoImage(file='pawn.gif')
        self.image_thudstone = tkinter.PhotoImage(file='thudstone.gif')

        #notation list box and scroll bars
        self.scrollbar = tkinter.Scrollbar(master, orient='vertical')
        self.listbox = tkinter.Listbox(master, yscrollcommand=self.scrollbar.set)
        self.listbox.config(width=30, font=("Courier", 10), selectmode='single')
        self.scrollbar.config(command=self.listbox.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.listbox.pack(side='right', fill='both', expand=1)

        #"status bar" frame
        self.canvas = tkinter.Canvas(root, width=BOARD_SIZE, height=BOARD_SIZE)
        self.canvas.pack(expand=True)
        self.clear_sprites_all()

        self.subframe = tkinter.Frame(master, height=50, borderwidth=2, relief='groove')
        self.subframe.pack(side='bottom')
        self.subframe2 = tkinter.Frame(self.subframe, height=50, borderwidth=2, relief='raised')
        self.subframe2.pack(side='right')

        #"status bar" labels for images and piece counts
        self.dwarf_count = tkinter.StringVar()
        self.troll_count = tkinter.StringVar()
        self.user_notice = tkinter.StringVar()

        self.subframe_label = tkinter.Label(master, textvariable=self.user_notice, width=80)
        self.subframe_label.pack(side='left')

        self.d = tkinter.Label(self.subframe, image=self.image_dwarf)
        self.d.pack(side='left')
        tkinter.Label(self.subframe, textvariable=self.dwarf_count).pack(side='left')
        self.t = tkinter.Label(self.subframe, image=self.image_troll)
        self.t.pack(side='left')
        tkinter.Label(self.subframe, textvariable=self.troll_count).pack(side='left')

        #playback controls
        self.subframe2_button1 = tkinter.Button(self.subframe2, text="|<<")
        self.subframe2_button1.pack(side='left')
        self.subframe2_button2 = tkinter.Button(self.subframe2, text=" < ")
        self.subframe2_button2.pack(side='left')
        self.subframe2_button3 = tkinter.Button(self.subframe2, text=" > ")
        self.subframe2_button3.pack(side='left')
        self.subframe2_button4 = tkinter.Button(self.subframe2, text=">>|")
        self.subframe2_button4.pack(side='left')

        #playback bindings
        self.subframe2_button1.bind('<Button-1>', self.goto_ply)
        self.subframe2_button2.bind('<Button-1>', self.goto_ply)
        self.subframe2_button3.bind('<Button-1>', self.goto_ply)
        self.subframe2_button4.bind('<Button-1>', self.goto_ply)

        menubar = tkinter.Menu(root)
        root.config(menu=menubar)
        game_dropdown = tkinter.Menu(menubar)
        option_dropdown = tkinter.Menu(menubar)

        #menubar dropdowns
        menubar.add_cascade(label="Game", menu=game_dropdown)
        menubar.add_cascade(label="Options", menu=option_dropdown)
        game_dropdown.new_branch = tkinter.Menu(game_dropdown)
        game_dropdown.add_cascade(label='New',menu=game_dropdown.new_branch)
        game_dropdown.new_branch.add_command(label='Classic', command=self.newgame_classic)
        game_dropdown.new_branch.add_command(label='Koom Valley', command=self.newgame_kvt)
        game_dropdown.new_branch.add_command(label='Klash', command=self.newgame_klash)
        game_dropdown.new_branch2 = tkinter.Menu(game_dropdown)
        game_dropdown.add_cascade(label='CPU Controlled',menu=game_dropdown.new_branch2)
        game_dropdown.new_branch2.add_checkbutton(label='Troll', variable=self.cpu_troll)
        game_dropdown.new_branch2.add_checkbutton(label='Dwarf', variable=self.cpu_dwarf)
        game_dropdown.add_command(label='Open', command=self.file_opengame)
        game_dropdown.add_command(label='Save', command=self.file_savegame)
        game_dropdown.add_command(label='Exit', command=sys.exit)
        option_dropdown.add_checkbutton(label='Compulsory Capturing', \
                                        variable=self.compulsory_capturing)
        option_dropdown.add_checkbutton(label='Allow Illegal Moves', \
                                        variable=self.allow_illegal_play)
        option_dropdown.add_checkbutton(label='Alternative Iconset', \
                                        variable=self.alt_iconset, \
                                        command=self.change_iconset)

    def change_iconset(self):
        """
        Toggles between the chess piece icon set or the iconset
        for the previous thud application.  Freely available source & use.
        # Copyright Marc Boeren
        # http://www.million.nl/thudboard/
        """
        try:
            if self.alt_iconset.get():
                self.image_troll = tkinter.PhotoImage(file='troll.gif')
                self.image_dwarf = tkinter.PhotoImage(file='dwarf.gif')
                self.image_thudstone = tkinter.PhotoImage(file='rock.gif')
                self.d.configure(image=self.image_dwarf)
                self.t.configure(image=self.image_troll)
            else:
                self.image_troll = tkinter.PhotoImage(file='rook.gif')
                self.image_dwarf = tkinter.PhotoImage(file='pawn.gif')
                self.image_thudstone = tkinter.PhotoImage(file='thudstone.gif')
                self.d.configure(image=self.image_dwarf)
                self.t.configure(image=self.image_troll)
        except Exception as e:
            print(e)
            self.user_notice.set("Required files not found--maintaining iconset")
            self.alt_iconset.set(not self.alt_iconset.get())
            self.change_iconset()

        self.sync_sprites()

    def goto_ply(self, event):
        """Advances or reverses game based on playback widgets"""
        button_clicked = {
            self.subframe2_button1: 0,
            self.subframe2_button2: max(self.displayed_ply - 1, 0),
            self.subframe2_button3: min(self.displayed_ply + 1, len(self.board.ply_list) - 1),
            self.subframe2_button4: len(self.board.ply_list) - 1
            }[event.widget]
        self.play_out_moves(self.board.ply_list, button_clicked)

    def update_ui(self):
        """Updates UI piece count to reflect current live pieces"""
        self.dwarf_count.set("Dwarfs Remaining: " + str(len(self.board.dwarfs)))
        self.troll_count.set("Trolls Remaining: " + str(len(self.board.trolls)))
        self.user_notice.set("")

    def file_opengame(self):
        """Displays file dialog and then plays out game to end"""
        side = {    'd': 'dwarf',
                    'T': 'troll',
                    'R': 'thudstone' }

        self.cpu_troll.set(False)
        self.cpu_dwarf.set(False)
        imported_plies = []        
        regex_ply_notation = r"([T|d|R])([A-HJ-P][0-9]+)-([A-HJ-P][0-9]+)(.*)"
        compiled_notation = re.compile(regex_ply_notation)
        
        filename = tkinter.filedialog.askopenfilename(title="Open Thudgame", \
                                              multiple=False, \
                                              filetypes=[('thud-game files', '*.thud')])
        if not filename:
            return
        
        with open(filename, "r") as thud_file:
            for i,line in enumerate(thud_file):
                m = compiled_notation.search(line)
                if m:
                    p = Ply(side.get(m.group(1)), \
                            Ply.notation_to_position(m.group(2)), \
                            Ply.notation_to_position(m.group(3)), \
                            list(map(Ply.notation_to_position, m.group(4).split('x')[1:])))
                    imported_plies.append(p)
                else:
                    piece_list = line.split(',')
                    if len(piece_list) == 41 or len(piece_list) == 40:
                        self.board.ruleset = 'classic'
                    elif 'dH9' in piece_list:
                        self.board.ruleset = 'kvt'
                    else:
                        self.board.ruleset = 'klash'
                        
        self.displayed_ply = 0
        if self.play_out_moves(imported_plies, len(imported_plies) - 1):
            self.play_out_moves(imported_plies, 0)

    def file_savegame(self):
        """Opens save dialog box and exports moves to text file (.thud)"""
        def tostr(token, piece_list):
            '''pc_string = []
            for np in piece_list:
                pc_string.append(token + str(np))'''
            pc_string = map(Ply.position_to_notation, piece_list)
            return (','+token).join(pc_string)
            
        filename = tkinter.filedialog.asksaveasfilename(title="Save Thudgame", \
                                              filetypes=[('thud-game files', '*.thud')])
        if not filename:
            return

        try:
            f = open(filename, 'w')
            first_string  = 'd' + tostr('d',self.board.get_default_positions('dwarf', self.board.ruleset))
            first_string += ',T' + tostr('T',self.board.get_default_positions('troll', self.board.ruleset))
            first_string += ',R' + tostr('R',self.board.get_default_positions('thudstone', self.board.ruleset))

            f.write(first_string + '\n')

            for k in self.board.ply_list:
                f.write(str(k) + '\n')
        except:
            pass

    def sync_sprites(self):
        """Clears all loaded sprites and reloads according to current game positions"""
        self.clear_sprites_all()
        for i in self.board.trolls.get_bits():
            self.create_sprite('troll', i)
        for i in self.board.dwarfs.get_bits():
            self.create_sprite('dwarf', i)
        for i in self.board.thudstone.get_bits():
            self.create_sprite('thudstone', i)

    def create_sprite(self, token, position):
        """Creates a sprite at the given notation and binds mouse events"""
        if token == 'troll':
            sprite = self.canvas.create_image(0,0, image=self.image_troll, anchor='nw')
        elif token == 'dwarf':
            sprite = self.canvas.create_image(0,0, image=self.image_dwarf, anchor='nw')
        elif token == 'thudstone':
            sprite = self.canvas.create_image(0,0, image=self.image_thudstone, anchor='nw')
            
        self.canvas.tag_bind(sprite, "<Button-1>", self.mouseDown)
        self.canvas.tag_bind(sprite, "<B1-Motion>", self.mouseMove)
        self.canvas.tag_bind(sprite, "<ButtonRelease-1>", self.mouseUp)

        self.sprites[position] = sprite
        self.move_sprite(sprite, position)

    def move_sprite(self, sprite, position):
        """Moves a piece to destination, resetting origin square to empty"""
        file, rank = Ply.position_to_tuple(position)
        
        self.canvas.coords(sprite, \
                           self.square_size * (file - 1), \
                           self.square_size * (rank - 1))
        self.sprites[position] = sprite

    def clear_sprite(self, sprite):
        """Removes sprite from canvas"""
        self.canvas.delete(sprite)

    def clear_sprites_all(self):
        """Removes all sprites on the canvas and re-adds gameboard image"""
        self.canvas.delete(self.canvas.find_all())
        board = self.canvas.create_image(0, 0, image=self.image_board, anchor='nw')
        self.canvas.tag_bind(board, "<Button-1>", self.boardClick)

    def newgame_classic(self):
        """Menu handler for creating a new classic game"""
        self.newgame_common('classic')

    def newgame_kvt(self):
        """Menu handler for creating a new kvt game"""
        self.newgame_common('kvt')

    def newgame_klash(self):
        """Menu handler for creating a new klash game"""
        self.newgame_common('klash')

    def newgame_common(self, ruleset='classic'):
        """Executes common commands for creating a new game"""
        self.board = Gameboard(ruleset)
        self.sync_sprites()
        self.listbox.delete(0, 'end')
        self.update_ui()
        self.review_mode = False

    def boardClick(self, event):
        """Responds to clicks that DO not occur by sprite (used for troll materialization"""
        notation = (int(event.x // self.square_size), int(event.y // self.square_size))
        position = notation[1] * self.board.BOARD_WIDTH + \
                   notation[0] + self.board.BOARD_WIDTH + 1
        
        if self.allow_illegal_play.get() or \
           (self.board.ruleset == 'klash' and \
           self.board.turn_to_act() == 'troll' and \
           self.board.klash_trolls < 6) and \
           position in self.board.get_default_positions('troll', 'classic'):
            ply = Ply('troll', position, position, '')
            self.board.add_troll(position)
            self.board.ply_list.append(ply)
            self.notate_move(ply)
            self.sync_sprites()

    def mouseDown(self, event):
        """This function will record the notation of all clicks
        determined to have landed on a sprite (see create_piece) """
        self.posx = event.x
        self.posy = event.y
        pickup_notation = (int(event.x // self.square_size), \
                           int(event.y // self.square_size))
        self.pickup = pickup_notation[1] * self.board.BOARD_WIDTH + \
                      pickup_notation[0] + self.board.BOARD_WIDTH + 1

        if self.review_mode:
            return
        elif self.cpu_troll.get() and self.board.turn_to_act() == 'troll' or \
             self.cpu_dwarf.get() and self.board.turn_to_act() == 'dwarf':
            return
        elif self.board.ruleset == 'kvt' and \
             self.board.ply_list and \
             self.board.ply_list[-1].token == 'troll' and \
             self.board.ply_list[-1].captured:
            if self.board.ply_list[-2].token == 'troll' and \
               self.board.ply_list[-3].token == 'troll' and \
               int(self.board.trolls[self.pickup]):
                return
            self.sprite_lifted = True
            self.canvas.tag_raise('current')
        elif self.selection_mode == 'selecting' or \
             self.allow_illegal_play.get() or \
             self.board.game_winner or \
             self.board.token_at(self.pickup) == self.board.turn_to_act() or \
             (int(self.board.thudstone[self.pickup]) and \
             self.board.turn_to_act() == 'dwarf' and \
             self.board.ruleset == 'kvt'):
            self.sprite_lifted = True
            self.canvas.tag_raise('current')

    def mouseMove(self, event):
        """Activated only on a mouseDown-able sprite, this keeps the piece attached to the mouse"""
        if self.sprite_lifted:
            self.canvas.move('current', event.x - self.posx, event.y - self.posy)
            self.posx = event.x
            self.posy = event.y

    def mouseUp(self, event):
        """
        After piece is dropped, call logic function and execute/revert move.
        This function also handles manual selection (noncompulsory capture) logic.
        """
        dropoff_notation = (int(event.x // self.square_size),
                            int(event.y // self.square_size))
        self.dropoff = dropoff_notation[1] * self.board.BOARD_WIDTH + \
                       dropoff_notation[0] + self.board.BOARD_WIDTH + 1

        if not self.sprite_lifted:
            return
        elif not self.compulsory_capturing.get():
            if self.selection_mode == 'false':
                valid = self.board.validate_move(self.pickup, self.dropoff)
                if valid[2]:
                    self.user_notice.set("Select each piece to be captured and click capturing piece to finish.")
                    self.selected_pieces = []
                    self.selection_mode = 'selecting'
                    self.pickup_remembered = self.pickup
                    self.dropoff_remembered = self.dropoff
                elif valid[0]:
                    self.execute_ply(Ply(self.board.token_at(self.pickup), \
                                         self.pickup, \
                                         self.dropoff, \
                                         []))
                else:
                    self.move_sprite(self.sprites[self.pickup], \
                                     self.pickup)
            elif self.selection_mode == 'selecting':
                self.user_notice.set("Piece at " + str(self.dropoff) + " selected")
                self.selected_pieces.append(self.dropoff)
                if self.dropoff == self.dropoff_remembered:
                    self.selection_mode = 'false'
                    valid = self.check_logic(Ply(self.board.token_at(self.pickup_remembered), \
                                                 self.pickup_remembered, \
                                                 self.dropoff_remembered,
                                                 self.selected_pieces))
                    if valid[0]:
                        self.execute_ply(valid[1])
                        self.board.game_winner = self.board.get_game_outcome()
                    else:
                        self.move_sprite(self.sprites[self.pickup_remembered], \
                                         self.pickup_remembered)
        else:
            valid = self.check_logic(Ply(self.board.token_at(self.pickup), \
                                         self.pickup, \
                                         self.dropoff, \
                                         []))
            if valid[0]:
                self.execute_ply(valid[1])
                self.board.game_winner = self.board.get_game_outcome()
            else:
                self.move_sprite(self.sprites[self.pickup], \
                                 self.pickup)
        if self.board.game_winner != None:
            self.review_mode = True
            self.user_notice.set(str(self.board.game_winner) + ' win!')
                
        self.sprite_lifted = False        
            
    def check_logic(self, ply):
        """
        Returns the submitted PLY if move/capture is legal else,
        return None-filled Ply, which will revert attemtped move on UI.
        """

        result = self.board.validate_move(ply.origin, ply.dest)

        if self.allow_illegal_play.get():
            result = {
                True: (True, True, ply.captured),
                False:(True, False, [])
                }[bool(ply.captured)]

        if result[1] or result[0]:
            if self.compulsory_capturing.get():
                approved_captures = result[2]
            else:
                approved_captures = set(ply.captured).intersection(set(result[2]))

            #if it would be a legal capture move, but no captures selected, invalid ply
            if not result[0] and result[1] and not approved_captures:
                return (False, Ply(None,None,None,None))
            #if a legal move, but not a legal capture, but capture is notated, invalid ply
            if result[0] and not result[1] and ply.captured:
                return (False, Ply(None,None,None,None))
            
            return (True, Ply(self.board.token_at(ply.origin), ply.origin, ply.dest, approved_captures))
        return (False, Ply(None,None,None,None))

    def execute_ply(self, fullply):
        """Shortcut function to execute all backend updates along with UI sprites"""
        for target in fullply.captured:
            self.clear_sprite(self.sprites[target])
        
        self.move_sprite(self.sprites[fullply.origin], fullply.dest)
        self.board.apply_ply(fullply)
        self.board.ply_list.append(fullply)
        self.notate_move(fullply)
        self.displayed_ply = len(self.board.ply_list) - 1

    def play_out_moves(self, ply_list, stop_at):
        def is_review_mode(last_ply):
            if last_ply >= len(self.board.ply_list) - 1:
                return False
            return True

        def notate_append(ply):
            self.board.ply_list.append(ply)
            self.notate_move(ply)
            
        """Go through ply list and execute each until stop_at number"""
        self.cpu_troll.set(False)
        self.cpu_dwarf.set(False)       
        self.newgame_common(self.board.ruleset)

        for a, b in enumerate(ply_list):
            if a <= stop_at:
                valid = self.board.validate_move(b.origin,b.dest)
                if self.allow_illegal_play.get():
                    self.board.apply_ply(b)
                    notate_append(b)
                    continue
                if len(b.captured) > len(valid[2]):
                    #if game notation is broken, and displays broken ply
                    notate_append(b)
                    self.user_notice.set('Illegal move/capture attempt at move: ' + \
                                         str((a+2.0)/2.0) + \
                                         ". Enable 'allow illegal moves' to see game as notated.")
                    return False
                elif valid[0] or valid[1]:
                    #valid move or cap
                    self.board.apply_ply(b)
                    notate_append(b)
                elif not valid[0] and not valid[1] and valid[2]:
                    #materializing troll
                    self.board.add_troll(b.origin)
                    notate_append(b)
            else:
                notate_append(b)

        self.sync_sprites()
        self.listbox.see(stop_at)
        self.displayed_ply = stop_at
        self.review_mode = is_review_mode(stop_at)
        return True

    def notate_move(self, ply):
        """Add move to the listbox of moves"""
        ply_num = str((len(self.board.ply_list) + 1)/2).ljust(5)
        self.listbox.insert('end', ply_num + str(ply))
        # Colorize alternating lines of the listbox
        for i in range(0,self.listbox.size(),2):
            self.listbox.itemconfigure(i, background='#f0f0ff')
            self.listbox.bind('<<ListboxSelect>>', self.click_listbox_left)
        self.listbox.yview_moveto(1.0)
        self.update_ui()

    def click_listbox_left(self, event):
        """Retrieves the clicked ply and play_out_move till that point"""
        try:
            self.displayed_ply = int(self.listbox.curselection()[0])
        except:
            self.displayed_ply = len(self.board.ply_list) - 1
        self.play_out_moves(self.board.ply_list, self.displayed_ply)

    def is_cpu_turn(self):
        """
        This is the function called 1/second to determine if CPU AI
        should begin calculating potential moves.
        """
        if self.cpu_troll.get() and self.board.turn_to_act() == 'troll' or \
           self.cpu_dwarf.get() and self.board.turn_to_act() == 'dwarf' and \
           not self.delay_ai and not self.review_mode and not self.board.game_winner:
            self.delay_ai = True
            self.user_notice.set("Computer is thinking...")
            try:
                ai_thread = threading.Thread(target=AIEngine.calculate_best_move(self.board, \
                                                                                 self.board.turn_to_act(), \
                                                                                 self.lookahead_count))
                ai_thread.start()
                ai_thread.join()
                self.execute_ply(ai.decision)
                self.delay_ai = False    
            except NoMoveException as ex:
                print("{0} has no moves available.".format(ex.token))
                self.delay_ai = True
            finally:
                self.board.game_winner = self.board.get_game_outcome()
                if not self.board.game_winner:
                    self.user_notice.set("")

            
                

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
        debug_troll, debug_dwarf = False, False
        best_cap, best_setup, best_move = None, None, None
        
        b = AIEngine(board)
        
        if not len(b.board.dwarfs): raise NoMoveException('dwarf')
        elif not len(b.board.trolls): raise NoMoveException('troll')
    
        if token == 'troll':
            b.threats = list(b.board.find_caps(token))
            b.setups = list(b.board.find_setups(token))
            b.moves = list(b.board.find_moves(token))
            
            immediate_threats = b.filter_adjacent_threats(token)
            if immediate_threats:
                ai.decision = b.filter_best(token, immediate_threats)
                if debug_troll: print('save', ai.decision.score, ai.decision or 'x')
            else:
                best_cap = b.filter_best(token, b.threats)
                best_setup = b.filter_best(token, b.setups)
                if debug_troll: print('cap', best_cap.score, best_cap or 'x')
                if debug_troll: print('setup', best_setup.score, best_setup or 'x')

                if lookahead and best_cap:
                    best_cap.score = AIEngine.predict_future(b.board, \
                                                             best_cap, \
                                                             lookahead, \
                                                             b.board.turn_to_act())
                    if debug_troll: print('future of cap', best_cap.score, best_cap)
                if lookahead and best_setup:
                    best_setup.score = AIEngine.predict_future(b.board, \
                                                               best_setup, \
                                                               lookahead, \
                                                               b.board.turn_to_act())
                    if debug_troll: print('future of setup', best_setup.score, best_setup)
                
                ai.decision = max(best_cap, best_setup)
                if not ai.decision:
                    ai.decision = b.filter_best(token, b.nonoptimal_troll_moves())
                    if debug_troll: print('move', ai.decision.score, ai.decision or 'x')
        elif token == 'dwarf':
            troll_cd = b.filter_capture_destinations(list(b.board.find_caps('troll')))
            
            b.threats = list(b.board.find_caps(token))
            b.setups = list(b.board.find_setups(token, Bitboard(troll_cd)))
            b.moves = list(b.board.find_moves(token))

            ai.decision = b.filter_best(token, b.threats)
            if debug_dwarf: print('cap', ai.decision.score, ai.decision or 'x')
            
            if not ai.decision:
                best_setup = b.filter_best(token, b.filter_farthest_dwarfs(b.setups))
                if debug_dwarf: print('setup', ai.decision.score, ai.decision or 'x')

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

                '''if lookahead and best_setup:
                    best_setup.score = AIEngine.predict_future(b.board, \
                                                               best_setup, \
                                                               lookahead, \
                                                               b.board.turn_to_act())
                    if debug_dwarf: print('future of setup', best_setup.score, best_setup)
                if lookahead and best_move:
                    best_move.score = AIEngine.predict_future(b.board, \
                                                              best_move, \
                                                              lookahead, \
                                                              b.board.turn_to_act())
                    if debug_dwarf: print('future of move', best_move.score, best_move)'''
                if best_setup and dest_more_dense(imap, best_setup):
                    ai.decision = max(best_setup, best_move)
                elif best_move:
                    ai.decision = best_move
            if not ai.decision:
                ai.decision = next(b.board.find_moves('dwarf'))
        if not ai.decision:
            raise NoMoveException(token)

class thudgame:    
    def simulate_set(self, trials=5):
        results = []
        for i in range(trials):
            results.append(self.simulate_game())
        print(results)

    def simulate_game(self):
        global ui
        print('game in progress...')
        ui.newgame_classic()
        ui.cpu_troll.set(True)
        ui.cpu_dwarf.set(True)
        while not ui.board.game_winner:
            ui.is_cpu_turn()
            if not len(ui.board.ply_list) % 10:
                print('Ply {0}: trolls {1} to dwarf {2}'.format( \
                    len(ui.board.ply_list), \
                    len(ui.board.trolls), \
                    len(ui.board.dwarfs)))                
        print('{0} win! trolls {1} to dwarf {2}'.format(ui.board.game_winner, \
                                                        len(ui.board.trolls), \
                                                        len(ui.board.dwarfs)))
        return ui.board.game_winner

    def play_game(self):
        global ui
        global root
        ui.newgame_classic()
        r = RepeatTimer(.2, ui.is_cpu_turn)
        r.start()
        root.mainloop()
    
ai = threading.local()
root = tkinter.Tk()
root.wm_resizable(0,0)
ui = DesktopGUI(root)

game = thudgame()
game.play_game()
#game.simulate_set(15)

