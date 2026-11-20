"""Plume mock-ups: four looks, 16x20 pixels, Sweetie 16 palette (same body as Quill)."""

HEAD = [
    "..kkkkkkkkkkkk..",
    ".kssssssssssssk.",
    ".kskkkkkkkkkksk.",
    ".ksktkttttktksk.",   # lashes: dark flick over the outer corner of each eye
    ".ksktaattaatksk.",
    ".ksktaattaatksk.",
    ".kskrttttttrksk.",   # rosy cheeks
    ".ksktttrrtttksk.",   # red smile
    ".kskkkkkkkkkksk.",
    ".kssssssssssmsk.",
    "..kkkkkkkkkkkk..",
]
LEGS = "....km....mk...."
BODY_TOP = "....kddddddk...."
BODY_BOTTOM = "...kkkkkkkkkk..."

# A: a ribbon bow tied on the antenna, small bow at the collar
BOW = [
    "...rrr....rrr...",
    "....rrroorrr....",
    "...rrr.kk.rrr...",
    ".......kk.......",
] + HEAD + [BODY_TOP, "...kddrrrrddk...", "...kdddrrdddk...", BODY_BOTTOM, LEGS]

# B: a feather ("plume") instead of the antenna, pearl necklace
FEATHER = [
    "..........www...",
    ".........wsww...",
    "........wsw.....",
    ".......kw.......",
] + HEAD + [BODY_TOP, "...kdwdwwdwdk...", "...kddddddddk...", BODY_BOTTOM, LEGS]

# C: receptionist headset over the head, ear cups at the sides, name badge
def cups(rows):
    out = list(rows)
    out[0] = "." + "p" + out[0][2:14] + "p" + "."           # band meets the head
    for i in (1, 2):
        out[i] = "p" + out[i][1:15] + "p"
    for i in (3, 4, 5, 6):                                  # ear cups
        out[i] = "p" + out[i][1:15] + "p"
    return out
HEADSET = [
    "................",
    "....pppppppp....",
    "...p...yy...p...",
    "..p....kk....p..",
] + cups(HEAD) + [BODY_TOP, "...kdddwwdddk...", "...kdddyydddk...", BODY_BOTTOM, LEGS]

# D: plum bob with a side-swept fringe, red scarf
def bob(rows):
    out = list(rows)
    out[0] = "..pppppppppppp.."
    out[1] = ".ppppppppsssspp."
    for i in range(2, 9):
        out[i] = "pp" + out[i][2:14] + "pp"
    out[9] = "p" + out[9][1:15] + "p"
    return out
BOB = [
    "................",
    ".......yy.......",
    ".......kk.......",
    "....pppppppp....",
] + bob(HEAD) + [BODY_TOP, "...krrrrrrrrk...", "...kddddrrddk...", BODY_BOTTOM, LEGS]

OPTIONS = {"A": ("Bow", BOW), "B": ("Feather", FEATHER), "C": ("Headset", HEADSET), "D": ("Bob & scarf", BOB)}
