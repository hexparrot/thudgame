"""A python3 implementation of the Thud! boardgame
"""

__author__ = "William Dizon"
__license__ = "MIT License"
__version__ = "1.8.0"
__email__ = "wdchromium@gmail.com"

from thudclasses import *
from thud import *

import copy
import tkinter
import tkinter.filedialog
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

class tkinter_game:    
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

if __name__ == '__main__':
    root = tkinter.Tk()
    root.wm_resizable(0,0)
    ui = DesktopGUI(root)

    game = tkinter_game()
    game.play_game()
    #game.simulate_set(15)
