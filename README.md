This is an implementation of Thud!, a boardgame by Trevor Truran, first published in 2002, inspired by the Discworld novels. 

It aims to offer both backwards compatibility with the existing Thud! application while adding new features such as drag-n-drop interface, computer opponents (AI) and support for all available rulesets including Koom Valley Thud!.

This app runs on Python3 and requires tkinter.  Often, Linux distros provide this as an installable package, e.g., `python3-tkinter`.

Run the game interactively:
`python3 gui.py`

Alternatively, `console.py` can be used to select the next move based on provided gamestate and does not use the GUI. This allows for easy access to AI opponent choices across different platforms. Save an in-progress game from the GUI to see expected formatting and game notation.

EXAMPLES:

```$ cat start.thud   # saved game after one move
dF1,dG1,dJ1,dK1,dE2,dL2,dD3,dM3,dC4,dN4,dB5,dO5,dA6,dP6,dA7,dP7,dA9,dP9,dA10,dP10,dB11,dO11,dC12,dN12,dD13,dM13,dE14,dL14,dF15,dG15,dJ15,dK15,TG7,TH7,TJ7,TG8,TJ8,TG9,TH9,TJ9,RH8
dO11-O9

$ python3 console.py next_move < start.thud
INFO: TROLL
INFO: turn: 0
INFO: # threats: 0
INFO: # setups: 24
INFO:   T: 32 d: 32

TG7-F7
```
