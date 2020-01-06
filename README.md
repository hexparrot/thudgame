This is an implementation of Thud!, a boardgame by Trevor Truran, first published in 2002, inspired by the Discworld novels. 

It aims to offer both backwards compatibility with the existing Thud! application while adding new features such as drag-n-drop interface, computer opponents (AI) and support for all available rulesets including Koom Valley Thud!.

This app runs on Python3 and has one additional dependencies, tkinter.  Often, Linux distros provide this as an installable package, e.g., `python3-tkinter`.

Run the game interactively:
`python3 gui.py`

Alternatively, `console.py` can be used to select the next move based on provided gamestate and does not use the GUI. This allows for easy access to AI opponent choices across different platforms. Save an in-progress game from the GUI to see expected formatting and game notation.

```python3 console.py next_move < output.thud
INFO: TROLL
INFO: turn: 0
INFO: # threats: 0
INFO: # setups: 24
INFO:   T: 32 d: 32

TG7-F7
```
