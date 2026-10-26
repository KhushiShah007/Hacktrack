"""Original pixel-art sprites drawn as character grids and rendered to crisp inline SVG.

Each grid row is a string; every character maps to a colour in the sprite's palette ('.' is
transparent). Horizontal runs of the same colour are merged into one <rect> to keep the SVG small.
`sprite()` is exposed to Jinja, and `write_static_tiles()` writes tiling backgrounds for CSS.
"""
import os
from functools import lru_cache

from markupsafe import Markup

K = "#1b1022"

AVATAR = [
    "....KKKKAA..",
    "...KHHHHKA..",
    "..KHHHHHHK..",
    "..KHSSSSHK..",
    "..KSESSESK..",
    "..KSSSSSSK..",
    "..KHSMMSHK..",
    "..KHKSSKHK..",
    "..KOOOOOOK..",
    ".KOOOWWOOOK.",
    ".KSKOOOOKSK.",
    "..KOOOOOOK..",
    "..KPPPPPPK..",
    "..KPPKKPPK..",
    "..KPK..KPK..",
    ".KBBK..KBBK.",
]
LOOKS = {
    "knight": {"H": "#f7d26b", "S": "#f5c9a6", "O": "#7b3fc4", "W": "#ffd23f", "P": "#4a2a7a", "B": "#3a2a1a", "A": None},
    "coder": {"H": "#3b2418", "S": "#c98f6b", "O": "#f4f4f4", "W": "#3df58a", "P": "#1f9e57", "B": "#ffffff", "A": "#ff7ac8"},
    "astro": {"H": "#1a1a2e", "S": "#8d5a3b", "O": "#4fd8ff", "W": "#ffffff", "P": "#2b5d9e", "B": "#1a1a2e", "A": None},
    "ranger": {"H": "#d9502b", "S": "#f1c27d", "O": "#3c8d3c", "W": "#a0522d", "P": "#5b3a1e", "B": "#2b1a0e", "A": None},
}

PIN = [
    "..KKKKK..",
    ".KRRRRRK.",
    "KRWRRRRRK",
    "KRRDDDRRK",
    "KRDDDDDRK",
    "KRRDDDRRK",
    "KRRRRRRRK",
    ".KRRRRRK.",
    ".KRRRRRK.",
    "..KRRRK..",
    "..KRRRK..",
    "...KRK...",
    "....K....",
]
PIN_MISSED = [
    "..KKKKK..",
    ".KRRRRRK.",
    "KRXRRRXRK",
    "KRRXRXRRK",
    "KRRRXRRRK",
    "KRRXRXRRK",
    "KRXRRRXRK",
    ".KRRRRRK.",
    ".KRRXRRK.",
    "..KRXRK..",
    "..KRRRK..",
    "...KRK...",
    "....K....",
]
PIN_COLOURS = {
    "red": {"R": "#e8322f", "W": "#ff9a8a", "D": "#2a0f0f"},
    "green": {"R": "#2fbf4f", "W": "#a6f5b8", "D": "#0f2a14"},
    "gold": {"R": "#ffc21a", "W": "#fff3b0", "D": "#5a3a00"},
    "grey": {"R": "#9a9aaa", "W": "#d8d8e0", "D": "#3a3a48"},
    "missed": {"R": "#6d6d7a", "X": "#1b1022"},
}

SPRITES = {
    "cat": ([
        ".K...K..........",
        "KGK.KGK.........",
        "KGGKGGK.........",
        "KGEGEGGK.....KK.",
        "KGGPGGGKKKKKKGK.",
        ".KGGGWGGGWGGGGK.",
        ".KGWGGGWGGGWGGK.",
        ".KGGGGGGGGGGGK..",
        "..KK.KK..KK.KK..",
    ], {"K": "#2a2a35", "G": "#b8b8c8", "W": "#e8e8f0", "E": K, "P": "#ff8fb1"}),
    "raccoon": ([
        ".K...K............",
        "KGK.KGK...........",
        "KWWWWWK...........",
        "DDEWWEDD.......KK.",
        "KWWNNWWKKKKKKKKDGK",
        ".KGGGGGGGGGGGGKGDK",
        ".KGGGGGGGGGGGGKDGK",
        "..KGGGGGGGGGGGK.K.",
        "..KGK.KGK.KGK.KGK.",
        "..KK..KK..KK..KK..",
    ], {"K": K, "G": "#8a8a96", "W": "#e8e8e8", "D": "#2a2a35", "N": K, "E": "#ffffff"}),
    "tree": ([
        ".....KK.....",
        "....KGGK....",
        "....KGgK....",
        "...KGGGGK...",
        "...KGgGGK...",
        "..KGGGGgGK..",
        "...KGGGGK...",
        "..KGgGGGGK..",
        ".KGGGGgGGGK.",
        "..KGGGGGGK..",
        ".KGGgGGGGGK.",
        "KGGGGGGgGGGK",
        "KKKKKKKKKKKK",
        ".....BB.....",
        ".....BB.....",
        "....KBBK....",
    ], {"K": "#0f3b1d", "G": "#1f8a3c", "g": "#45c35a", "B": "#7a4a26"}),
    "pine2": ([
        "....KKKK....",
        "..KKGGgGKK..",
        ".KGGGGGGgGK.",
        "KGGgGGGGGGGK",
        "KGGGGGgGGGGK",
        "KGgGGGGGGgGK",
        ".KGGGgGGGGK.",
        "..KKGGGGKK..",
        "....KBBK....",
        ".....BB.....",
        ".....BB.....",
        "....KBBK....",
    ], {"K": "#0f3b1d", "G": "#2f9e44", "g": "#7fe06a", "B": "#7a4a26"}),
    "sunflower": ([
        "..YYY..",
        ".YYOYY.",
        "YYOOOYY",
        ".YYOYY.",
        "..YYY..",
        "...g...",
        ".LLg...",
        "..Lg...",
        "...gLL.",
        "...gL..",
        "...g...",
        "...g...",
    ], {"Y": "#ffd23f", "O": "#7a4a26", "g": "#2e8b3a", "L": "#45c35a"}),
    "flowers": ([
        ".R...P.",
        "RYR.PYP",
        ".R...P.",
        ".g...g.",
        "..g.g..",
        "...g...",
    ], {"R": "#ff5f7e", "P": "#b48cff", "Y": "#ffd23f", "g": "#2e8b3a"}),
    "mushroom": ([
        "..KKKK..",
        ".KRRWRK.",
        "KRWRRRRK",
        "KRRRRWRK",
        "KKKKKKKK",
        "..KSSK..",
        "..KSSK..",
        "..KKKK..",
    ], {"K": "#3a1010", "R": "#e23d3d", "W": "#ffffff", "S": "#f5e6c8"}),
    "log": ([
        ".KKKKKKKKKKKK.",
        "KBBbBBBBbBBKOK",
        "KBBBBbBBBBBKoK",
        "KBbBBBBBBbBKOK",
        ".KKKKKKKKKKKK.",
    ], {"K": "#3a2010", "B": "#8b5a2b", "b": "#6b3f1b", "O": "#d9a066", "o": "#b07a3f"}),
    "bush": ([
        "...KKKK.....",
        ".KKgGGGKKK..",
        "KGGGGgGGGGK.",
        "KGgGGGGGgGK.",
        ".KKKKKKKKK..",
    ], {"K": "#0f3b1d", "G": "#2f9e44", "g": "#7fe06a"}),
    "cloud": ([
        "......WWWW......",
        "...WWWWWWWWW.WW.",
        "..WWWWWWWWWWWWWW",
        ".WWWWWWWWWWWWWWW",
        "PPPPPPPPPPPPPPPP",
        ".PPPPPPPPPPPPPP.",
    ], {"W": "#ffffff", "P": "#d6e6ff"}),
    "cloud_night": ([
        "......WWWW......",
        "...WWWWWWWWW.WW.",
        "..WWWWWWWWWWWWWW",
        ".WWWWWWWWWWWWWWW",
        "PPPPPPPPPPPPPPPP",
        ".VVVVVVVVVVVVVV.",
    ], {"W": "#ffd6ef", "P": "#ff8fd0", "V": "#7a5cff"}),
    "star": ([
        "...Y...",
        "...Y...",
        "..YWY..",
        "YYWWWYY",
        "..YWY..",
        "...Y...",
        "...Y...",
    ], {"Y": "#ffd23f", "W": "#ffffff"}),
    "coin": ([
        "..KKKK..",
        ".KYYYYK.",
        "KYYWYYOK",
        "KYWYYYOK",
        "KYYYYYOK",
        "KYYYYYOK",
        ".KOOOOK.",
        "..KKKK..",
    ], {"K": "#5a3a00", "Y": "#ffd23f", "W": "#fff6c2", "O": "#d99a1e"}),
    "trophy": ([
        "..KKKKKKKK..",
        "KKKYWYYYOKKK",
        "KYKYWYYYOKYK",
        "KYKYWYYYOKYK",
        ".KKYYYYYOKK.",
        "..KYYYYYOK..",
        "...KYYYOK...",
        "....KYOK....",
        "....KYOK....",
        "...KKKKKK...",
        "..KBBBBBBK..",
        "..KKKKKKKK..",
    ], {"K": "#5a3a00", "Y": "#ffd23f", "W": "#fff6c2", "O": "#d99a1e", "B": "#7a4a26"}),
    "door": ([
        "...SSSSSS...",
        "..SSWWWWSS..",
        ".SSWBBBBWSS.",
        ".SWBBbBBBWS.",
        "SSWBbBBbBWSS",
        "SWBBbBBbBBWS",
        "SWBBbBBbBBWS",
        "SWBBbBBbBBWS",
        "SWBBbBYbBBWS",
        "SWBBbBBbBBWS",
        "SWBBbBBbBBWS",
        "SWBBbBBbBBWS",
        "SSWBbBBbBWSS",
        "SSWWWWWWWWSS",
    ], {"S": "#9aa0b5", "W": "#5b3a1e", "B": "#c47a2c", "b": "#8b4f1c", "Y": "#ffd23f"}),
    "heart": ([
        ".RR.RR.",
        "RWRRRRR",
        "RRRRRRR",
        ".RRRRR.",
        "..RRR..",
        "...R...",
    ], {"R": "#ff3b5c", "W": "#ffffff"}),
    "flame": ([
        "...R...",
        "..RR...",
        "..RRR.R",
        ".RROR.R",
        ".ROORRR",
        "RROYORR",
        "ROYYYOR",
        "ROYYYOR",
        ".RROOR.",
    ], {"R": "#ff4b2b", "O": "#ff9a2b", "Y": "#ffe14d"}),
    "scroll": ([
        ".KKKKKKK.",
        "KTTTTTTTK",
        ".KTLLLTK.",
        ".KTTTTTK.",
        ".KTLLLTK.",
        ".KTTTTTK.",
        "KTTTTTTTK",
        ".KKKKKKK.",
    ], {"K": "#5b3a1e", "T": "#f3e1b6", "L": "#8b6b3e"}),
    "laptop": ([
        ".KKKKKKKK.",
        ".KCCCCCCK.",
        ".KCcCCCCK.",
        ".KCCCCCCK.",
        ".KKKKKKKK.",
        "KGGGGGGGGK",
        "KKKKKKKKKK",
    ], {"K": K, "C": "#4fd8ff", "c": "#ffffff", "G": "#9aa0b5"}),
    "sword": ([
        ".......KK",
        "......KWK",
        ".....KWK.",
        "....KWK..",
        "KK.KWK...",
        ".KKWK....",
        "..KYK....",
        ".KYKKK...",
        "KYK......",
    ], {"K": K, "W": "#e8e8f0", "Y": "#ffd23f"}),
    "briefcase": ([
        "...KKKK...",
        "...K..K...",
        "KKKKKKKKKK",
        "KBBBBBBBBK",
        "KBBBYYBBBK",
        "KBBBBBBBBK",
        "KBBBBBBBBK",
        "KKKKKKKKKK",
    ], {"K": K, "B": "#a0522d", "Y": "#ffd23f"}),
    "wrench": ([
        ".KK...KK.",
        ".KGK.KGK.",
        ".KGGKGGK.",
        "..KGGGK..",
        "...KGK...",
        "...KGK...",
        "...KGK...",
        "...KGK...",
        "...KKK...",
    ], {"K": K, "G": "#c0c6d6"}),
    "flask": ([
        "...KKK...",
        "...KWK...",
        "...KWK...",
        "..KWWWK..",
        ".KWWWWWK.",
        ".KWGGGWK.",
        "KWGGgGGWK",
        "KGGGGGgGK",
        "KKKKKKKKK",
    ], {"K": K, "W": "#dff7ff", "G": "#3df58a", "g": "#ffffff"}),
    "crt": ([
        "KKKKKKKKKKKKKK",
        "KWWWWWWWWWWWWK",
        "KWBBBBBBBBBBWK",
        "KWBGBBBBBBBBWK",
        "KWBBBBBBBBBBWK",
        "KWBBBBBBBBBBWK",
        "KWBBBBBBBBBBWK",
        "KWWWWWWWWWWGWK",
        "KKKKKKKKKKKKKK",
        ".....KWWK.....",
        "...KKKKKKKK...",
    ], {"K": K, "W": "#bfe9f2", "B": "#0b0b2b", "G": "#3df58a"}),
}

ICONS = {
    "home": ["...XX...", "..XXXX..", ".XXXXXX.", "XXXXXXXX", ".X....X.", ".X.XX.X.", ".X.XX.X.", ".XXXXXX."],
    "map": ["XX..XX..", "X.XX.XXX", "X.X..X.X", "X.X..X.X", "X.X..X.X", "X.X..X.X", "XXX.XX.X", "..XX..XX"],
    "board": ["XX.XX.XX", "XX.XX.XX", "XX.XX.XX", "XX.XX...", "XX.XX.XX", "XX....XX", "XX......", "XX......"],
    "list": ["X.XXXXXX", "........", "X.XXXXXX", "........", "X.XXXXXX", "........", "X.XXXXXX", "........"],
    "plus": ["...XX...", "...XX...", "...XX...", "XXXXXXXX", "XXXXXXXX", "...XX...", "...XX...", "...XX..."],
    "bell": ["...XX...", "..XXXX..", ".XXXXXX.", ".XXXXXX.", ".XXXXXX.", "XXXXXXXX", "........", "...XX..."],
    "chart": ["......XX", "......XX", "...XX.XX", "...XX.XX", "XX.XX.XX", "XX.XX.XX", "XX.XX.XX", "XXXXXXXX"],
    "party": [".XX..XX.", ".XX..XX.", "........", "XXXXXXXX", "XXXXXXXX", "XXXXXXXX", "XX.XX.XX", "........"],
    "feed": ["......X.", "....XXX.", "XXXXXXX.", "XXXXXXXX", "XXXXXXX.", ".X..XXX.", ".X....X.", ".X......"],
    "book": ["XXXXXXX.", "X.....XX", "X.XXX.XX", "X.....XX", "X.XXX.XX", "X.....XX", "XXXXXXXX", ".XXXXXXX"],
    "chest": [".XXXXXX.", "X......X", "XXXXXXXX", "X..XX..X", "X..XX..X", "X......X", "XXXXXXXX", "........"],
    "trophy": ["XXXXXXXX", "X.XXXX.X", "X.XXXX.X", ".XXXXXX.", "..XXXX..", "...XX...", "..XXXX..", ".XXXXXX."],
    "gear": ["...XX...", ".XXXXXX.", ".XX..XX.", "XX....XX", "XX....XX", ".XX..XX.", ".XXXXXX.", "...XX..."],
    "logout": ["XXXXX...", "X...X...", "X...X.X.", "X.X.XXXX", "X...X.X.", "X...X...", "X...X...", "XXXXX..."],
    "search": [".XXXX...", "X....X..", "X....X..", "X....X..", ".XXXX...", ".....XX.", "......XX", ".......X"],
    "calendar": [".X..X...", "XXXXXXXX", "XXXXXXXX", "X......X", "X.X.X..X", "X......X", "X.X.X..X", "XXXXXXXX"],
    "download": ["...XX...", "...XX...", "...XX...", ".XXXXXX.", "..XXXX..", "...XX...", "X......X", "XXXXXXXX"],
    "upload": ["...XX...", "..XXXX..", ".XXXXXX.", "...XX...", "...XX...", "...XX...", "X......X", "XXXXXXXX"],
    "edit": ["......XX", ".....XXX", "....XXX.", "...XXX..", "..XXX...", ".XXX....", "XX......", "XXX....."],
    "trash": ["..XXXX..", "XXXXXXXX", ".X....X.", ".X.X.XX.", ".X.X.XX.", ".X.X.XX.", ".X....X.", ".XXXXXX."],
    "check": ["........", ".......X", "......XX", "X....XX.", "XX..XX..", ".XXXX...", "..XX....", "........"],
    "sun": ["X..X..X.", ".X.X.X..", "..XXX...", "XXXXXXX.", "..XXX...", ".X.X.X..", "X..X..X.", "........"],
    "moon": ["..XXX...", ".XX.....", "XX......", "XX......", "XX......", "XX.....X", ".XX..XX.", "..XXXX.."],
    "close": ["XX....XX", ".XX..XX.", "..XXXX..", "...XX...", "..XXXX..", ".XX..XX.", "XX....XX", "........"],
    "external": ["...XXXXX", "......XX", ".....X.X", "XXX.X..X", "X..X....", "X.......", "X.....X.", "XXXXXXX."],
    "copy": ["XXXXX...", "X...X...", "X.XXXXXX", "X.X....X", "XXX....X", "..X....X", "..X....X", "..XXXXXX"],
    "star": ["...XX...", "...XX...", "XXXXXXXX", ".XXXXXX.", "..XXXX..", ".XXXXXX.", ".XX..XX.", "X......X"],
    "bolt": ["....XXX.", "...XXX..", "..XXX...", ".XXXXXX.", "...XXX..", "..XXX...", ".XX.....", "X......."],
    "user": ["..XXXX..", "..XXXX..", "..XXXX..", "...XX...", ".XXXXXX.", "XXXXXXXX", "XXXXXXXX", "XXXXXXXX"],
    "warning": ["...XX...", "..XXXX..", "..X..X..", ".XX..XX.", ".XXXXXX.", "XXX..XXX", "XXXXXXXX", "........"],
    "eye": ["........", "..XXXX..", ".X....X.", "X..XX..X", "X..XX..X", ".X....X.", "..XXXX..", "........"],
}

TYPE_ICONS = {"hackathon": "laptop", "competition": "sword", "internship": "briefcase",
              "scholarship": "scroll", "workshop": "wrench", "research": "flask"}


def grid_to_rects(grid, palette):
    """Merge horizontal runs into rects. Yields (x, y, w, colour)."""
    for y, row in enumerate(grid):
        x = 0
        while x < len(row):
            ch = row[x]
            colour = palette.get(ch)
            if ch == "." or not colour:
                x += 1
                continue
            run = 1
            while x + run < len(row) and row[x + run] == ch:
                run += 1
            yield x, y, run, colour
            x += run


@lru_cache(maxsize=512)
def svg(grid_key, scale=4, cls="", label="", variant=""):
    grid, palette = _resolve(grid_key, variant)
    width = max(len(r) for r in grid)
    height = len(grid)
    rects = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{c}"/>'
                    for x, y, w, c in grid_to_rects(grid, palette))
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    title = f"<title>{label}</title>" if label else ""
    return (f'<svg class="sprite sprite-{grid_key} {cls}" xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {width} {height}" width="{width * scale}" height="{height * scale}" '
            f'shape-rendering="crispEdges" {aria}>{title}{rects}</svg>')


def _resolve(key, variant):
    if key == "avatar":
        palette = {"K": K, "E": K, "M": "#c0392b", **LOOKS.get(variant or "knight", LOOKS["knight"])}
        return AVATAR, palette
    if key == "pin":
        colours = PIN_COLOURS.get(variant or "red", PIN_COLOURS["red"])
        return (PIN_MISSED if variant == "missed" else PIN), {"K": K, **colours}
    if key.startswith("icon-"):
        return ICONS[key[5:]], {"X": "currentColor"}
    grid, palette = SPRITES[key]
    return grid, palette


def sprite(name, scale=4, cls="", label="", variant=""):
    """Jinja helper: {{ sprite('cat', 3) }} or {{ sprite('avatar', 4, variant='coder') }}."""
    try:
        return Markup(svg(name, scale, cls, label, variant))
    except KeyError:
        return Markup("")


def icon(name, size=16, cls="", label=""):
    """Pixel icon that inherits the text colour."""
    try:
        return Markup(svg(f"icon-{name}", max(1, size // 8), f"icon {cls}".strip(), label, ""))
    except KeyError:
        return Markup("")


def type_icon(qtype, scale=3, cls=""):
    return sprite(TYPE_ICONS.get(qtype, "star"), scale, cls)


TILES = {
    "grass": ([
        "................",
        "...d............",
        "..d.d.......l...",
        "...........l.l..",
        "................",
        "......l.........",
        ".....l.l........",
        "................",
        "..........d.....",
        ".........d.d....",
        "................",
        ".l..............",
        "l.l.............",
        "............d...",
        "...........d.d..",
        "................",
    ], {"d": "#47b13a", "l": "#8be274"}),
    "grass_night": ([
        "................",
        "...d............",
        "..d.d.......l...",
        "...........l.l..",
        "................",
        "......l.........",
        ".....l.l........",
        "................",
        "..........d.....",
        ".........d.d....",
        "................",
        ".l..............",
        "l.l.............",
        "............d...",
        "...........d.d..",
        "................",
    ], {"d": "#173d3a", "l": "#2f6f5f"}),
    "bricks": ([
        "hhhhhhhDhhhhhhhD",
        "RRRRRRRDRRRRRRRD",
        "RRRRRRRDRRRRRRRD",
        "DDDDDDDDDDDDDDDD",
        "hhhDhhhhhhhDhhhh",
        "RRRDRRRRRRRDRRRR",
        "RRRDRRRRRRRDRRRR",
        "DDDDDDDDDDDDDDDD",
    ], {"R": "#c1533b", "D": "#7a2a1e", "h": "#d9734e"}),
    "stone": ([
        "hhhhhhhDhhhhhhhD",
        "SSSSSSSDSSSSSSSD",
        "SSSSSSSDSSSSSSSD",
        "DDDDDDDDDDDDDDDD",
        "hhhDhhhhhhhDhhhh",
        "SSSDSSSSSSSDSSSS",
        "SSSDSSSSSSSDSSSS",
        "DDDDDDDDDDDDDDDD",
    ], {"S": "#6c6f8a", "D": "#3b3d55", "h": "#8a8eab"}),
    "stars": ([
        "................................",
        "..W.............................",
        "..........................c.....",
        "................................",
        "..............p.................",
        "................................",
        "................................",
        "......................W.........",
        "................................",
        ".c..............................",
        "................................",
        "...........W....................",
        "................................",
        "..........................W.....",
        "................................",
        "................................",
        ".....p..........................",
        "................................",
        "................................",
        "...................c............",
        "................................",
        "................................",
        "W...............................",
        "............................p...",
        "................................",
        "..........W.....................",
        "................................",
        "................................",
        "...................W............",
        "................................",
        "...c............................",
        "................................",
    ], {"W": "#ffffff", "c": "#4fd8ff", "p": "#ff8fd0"}),
}


def write_static_tiles(static_dir):
    """Write tile SVGs used as CSS backgrounds (idempotent). # CO2 file handling"""
    out = os.path.join(static_dir, "sprites")
    os.makedirs(out, exist_ok=True)
    for name, (grid, palette) in TILES.items():
        width, height = max(len(r) for r in grid), len(grid)
        rects = "".join(f'<rect x="{x}" y="{y}" width="{w}" height="1" fill="{c}"/>'
                        for x, y, w, c in grid_to_rects(grid, palette))
        content = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
                   f'width="{width * 4}" height="{height * 4}" shape-rendering="crispEdges">{rects}</svg>')
        path = os.path.join(out, f"{name}.svg")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError:
            pass  # read-only deploys still render; tiles are also committed to the repo
    for name in ("avatar", "pin", "trophy", "coin", "heart"):
        try:
            with open(os.path.join(out, f"{name}.svg"), "w", encoding="utf-8") as fh:
                fh.write(svg(name, 4))
        except OSError:
            pass
