"""Pixel-art sprites for Quill and Plume, drawn in the Sweetie 16 palette.

Each sprite is a list of equal-length strings; one character = one pixel.
'.' is transparent. Rendered in the terminal with half-block characters,
so two pixel rows fit in one text row and pixels come out square.
"""

PALETTE = {
    "k": "#1a1c2c",  # outline / near-black
    "p": "#5d275d",  # plum
    "r": "#b13e53",  # red
    "o": "#ef7d57",  # orange
    "y": "#ffcd75",  # yellow
    "l": "#a7f070",  # lime
    "g": "#38b764",  # green
    "t": "#257179",  # teal
    "n": "#29366f",  # navy
    "b": "#3b5dc9",  # blue
    "c": "#41a6f6",  # sky
    "a": "#73eff7",  # aqua
    "w": "#f4f4f4",  # white
    "s": "#94b0c2",  # light grey
    "m": "#566c86",  # grey
    "d": "#333c57",  # dark slate
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



def _loading(gap, dots):
    """Thinking: each eye is a little loading square, a 2x2 block with one pixel missing.
    The gap goes round clockwise (gap 0-3), while the dots of the mouth fill in (1-3)."""
    rows = [list("tttttttt") for _ in range(5)]
    for x in (1, 5):  # left eye, right eye
        for i, (r, dx) in enumerate(((1, 0), (1, 1), (2, 1), (2, 0))):  # TL, TR, BR, BL
            rows[r][x + dx] = "t" if i == gap else "a"
    for d in range(dots):
        rows[4][1 + 2 * d] = "a"
    return ["".join(r) for r in rows]


for _gap in range(4):
    for _dots in (1, 2, 3):
        FACES[f"load{_gap}{_dots}"] = _loading(_gap, _dots)

# Something failed: X eyes and a frown.
FACES["oops"] = ["atattata", "tattttat", "atattata", "ttaaaatt", "tattttat"]

BULB = {"idle": "y", "think": "a", "work": "o", "ask": "r", "off": "m", "happy": "l", "oops": "r"}


def frame(face="idle", bulb="idle"):
    rows = [list(r) for r in ROBOT]
    for i, line in enumerate(FACES[face]):
        rows[5 + i][4:12] = list(line)
    rows[0][7] = rows[0][8] = BULB[bulb]
    return ["".join(r) for r in rows]


# ---------------------------------------------------------------------------
# Plume (option B of the mock-ups): Quill's body with a feather ("plume") in
# place of the antenna, eyelashes, rosy cheeks, a red smile and pearls.
# Her face lives on rows 7-11, columns 4-11; the feather tip (row 0) shows her mood.
# ---------------------------------------------------------------------------

PLUME = [
    "..........www...",
    ".........wsww...",
    "........wsw.....",
    ".......kw.......",
    "..kkkkkkkkkkkk..",
    ".kssssssssssssk.",
    ".kskkkkkkkkkksk.",
    ".ksktkttttktksk.",
    ".ksktaattaatksk.",
    ".ksktaattaatksk.",
    ".kskrttttttrksk.",
    ".ksktttrrtttksk.",
    ".kskkkkkkkkkksk.",
    ".kssssssssssmsk.",
    "..kkkkkkkkkkkk..",
    "....kddddddk....",
    "...kdwdwwdwdk...",
    "...kddddddddk...",
    "...kkkkkkkkkk...",
    "....km....mk....",
]

PLUME_TIP = {"idle": "w", "think": "a", "work": "o", "ask": "r", "off": "m", "happy": "l",
             "oops": "r"}

CHARACTERS = ("quill", "plume")


def plume_frame(face="idle", bulb="idle"):
    rows = [list(r) for r in PLUME]
    lines = [list(l) for l in FACES[face]]
    if "a" not in lines[0]:
        lines[0][1] = lines[0][6] = "k"           # lashes, unless the eyes moved up there
    for i in (3, 4):                              # her mouth is red
        lines[i] = ["r" if c == "a" else c for c in lines[i]]
    if lines[3][0] == "t":
        lines[3][0] = "r"                         # cheeks
    if lines[3][7] == "t":
        lines[3][7] = "r"
    for i, line in enumerate(lines):
        rows[7 + i][4:12] = line
    rows[0][10:13] = [PLUME_TIP[bulb]] * 3
    return ["".join(r) for r in rows]


def sprite(who="quill", face="idle", bulb="idle"):
    return plume_frame(face, bulb) if who == "plume" else frame(face, bulb)
