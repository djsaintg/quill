"""Pixel-art sprites for Quill, drawn in the Sweetie 16 palette (same as Crew).

Each sprite is a list of equal-length strings; one character = one pixel.
'.' is transparent. Rendered in the terminal with half-block characters,
so two pixel rows fit in one text row and pixels come out square.
"""

PALETTE = {
    "k": "#1a1c2c",  # outline / near-black (Crew --bg)
    "p": "#5d275d",  # plum
    "r": "#b13e53",  # red
    "o": "#ef7d57",  # orange
    "y": "#ffcd75",  # yellow (Crew --warn)
    "l": "#a7f070",  # lime
    "g": "#38b764",  # green (Crew --good)
    "t": "#257179",  # teal
    "n": "#29366f",  # navy
    "b": "#3b5dc9",  # blue
    "c": "#41a6f6",  # sky (Crew --accent)
    "a": "#73eff7",  # aqua
    "w": "#f4f4f4",  # white (Crew --ink)
    "s": "#94b0c2",  # light grey (Crew --muted)
    "m": "#566c86",  # grey (Crew --line)
    "d": "#333c57",  # dark slate (Crew --card)
}

# --- Option A: the owl clerk (spectacles, quill tucked behind the ear) ---
OWL = [
    "..k..........k..",
    "..kk........kkww",
    "..kpk......kpkws",
    "..kppkkkkkkppkw.",
    ".kppppppppppppk.",
    ".kpmmmmppmmmmpk.",
    "kpmwwwwmmwwwwmpk",
    "kpmwkkwmmwkkwmpk",
    "kpmwkwwmmwkwwmpk",
    "kpmwwwwmmwwwwmpk",
    "kppmmmmoommmmppk",
    "kpppppkookpppppk",
    "kppyyyyyyyyyyppk",
    "kpyywyywyywyyypk",
    "kpyyyyyyyyyyyypk",
    ".kpyywyywyywypk.",
    "..kkyyyyyyyykk..",
    "...kokk..kkok...",
]

# --- Option B: the living inkwell (quill feather sticking out the top) ---
INKWELL = [
    "...........kk...",
    "..........kwwk..",
    ".........kwswk..",
    "........kwswk...",
    ".......kwswk....",
    "......kkmkk.....",
    ".....kdmddk.....",
    ".....kddddk.....",
    "...kkddddddkk...",
    "..knnnnnnnnnnk..",
    ".knbbbbbbbbbbnk.",
    ".knbwwbbbbwwbnk.",
    ".knbwkbbbbwkbnk.",
    ".knbbbbbbbbbbnk.",
    ".knbbkbbbbkbbnk.",
    ".knnbbkkkkbbnnk.",
    "..knnnnnnnnnnk..",
    "...kkkkkkkkkk...",
]

# --- Option C: the sticky note (folded corner, writing lines) ---
NOTE = [
    ".kkkkkkkkkkkkkk.",
    ".kyyyyyyyyyyyyk.",
    ".kyyyyyyyyyyyyk.",
    ".kyykkyyyykkyyk.",
    ".kyykwyyyykwyyk.",
    ".kyykkyyyykkyyk.",
    ".kyryyyyyyyyryk.",
    ".kyyyykyykyyyyk.",
    ".kyyyyykkyyyyyk.",
    ".kyyyyyyyyyyyyk.",
    ".kymmmmmmmmyyyk.",
    ".kyyyyyyyyyyyyk.",
    ".kymmmmmmyykkkk.",
    ".kyyyyyyyykook..",
    ".kymmmmyyykok...",
    ".kyyyyyyyykk....",
    ".kkkkkkkkkk.....",
    "................",
]

# --- Option D: the desk robot (CRT head, collar and tie) ---
ROBOT = [
    ".......yy.......",
    ".......kk.......",
    "..kkkkkkkkkkkk..",
    ".kssssssssssssk.",
    ".kskkkkkkkkkksk.",
    ".kskttttttttksk.",
    ".ksktaattaatksk.",
    ".ksktaattaatksk.",
    ".kskttttttttksk.",
    ".ksktttaatttksk.",
    ".kskkkkkkkkkksk.",
    ".kssssssssssmsk.",
    "..kkkkkkkkkkkk..",
    "....kddddddk....",
    "...kddwrwdddk...",
    "...kdddrddddk...",
    "...kkkkkkkkkk...",
    "....km....mk....",
]

OPTIONS = {
    "A": ("Owl clerk", OWL),
    "B": ("Inkwell", INKWELL),
    "C": ("Sticky note", NOTE),
    "D": ("Desk robot", ROBOT),
}


def check(sprite):
    widths = {len(r) for r in sprite}
    assert len(widths) == 1, f"ragged rows: {widths}"
    bad = {ch for r in sprite for ch in r if ch != "." and ch not in PALETTE}
    assert not bad, f"unknown colours: {bad}"


# ---------------------------------------------------------------------------
# Quill's animation frames (the desk robot, option D).
# The face lives on the screen: rows 5-9, columns 4-11 of ROBOT.
# The antenna bulb (row 0, columns 7-8) shows Quill's mood at a glance.
# ---------------------------------------------------------------------------

FACES = {
    "idle":    ["tttttttt", "taattaat", "taattaat", "tttttttt", "tttaattt"],
    "blink":   ["tttttttt", "tttttttt", "taattaat", "tttttttt", "tttaattt"],
    "talk1":   ["tttttttt", "taattaat", "taattaat", "tttaattt", "tttaattt"],
    "talk2":   ["tttttttt", "taattaat", "taattaat", "tttttttt", "ttaaaatt"],
    "think1":  ["taattaat", "taattaat", "tttttttt", "tttttttt", "tatttttt"],
    "think2":  ["taattaat", "taattaat", "tttttttt", "tttttttt", "tatatttt"],
    "think3":  ["taattaat", "taattaat", "tttttttt", "tttttttt", "tatatatt"],
    "workL":   ["tttttttt", "aattaatt", "aattaatt", "tttttttt", "tttaattt"],
    "workR":   ["tttttttt", "ttaattaa", "ttaattaa", "tttttttt", "tttaattt"],
    "ask":     ["taattaat", "taattaat", "taattaat", "tttttttt", "ttaaaatt"],
    "happy":   ["tttttttt", "taattaat", "attaatta", "tttttttt", "taaaaaat"],
    "sad":     ["tttttttt", "taattaat", "tttttttt", "ttaaaatt", "tattttat"],
}

BULB = {"idle": "y", "think": "a", "work": "o", "ask": "r", "off": "m", "happy": "l"}


def frame(face="idle", bulb="idle"):
    rows = [list(r) for r in ROBOT]
    for i, line in enumerate(FACES[face]):
        rows[5 + i][4:12] = list(line)
    rows[0][7] = rows[0][8] = BULB[bulb]
    return ["".join(r) for r in rows]
