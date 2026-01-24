"""
Contraction Detector for UEB Grade 2 Braille

This module provides an algorithm to detect and highlight contractions
in Grade 2 UEB braille translation. It compares the contracted (G2)
translation with the uncontracted (G1) translation to identify where
contractions were applied.

The output format is a list of "spans" that identify:
- The contraction type (if identifiable)
- The print text that was contracted
- The braille representation
- Position mappings for both print and braille
"""

import os
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# Add the python directory to the path for the louis module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

# Set library path for ctypes to find liblouis
os.environ['DYLD_LIBRARY_PATH'] = os.path.join(os.path.dirname(__file__), 'liblouis', '.libs')

# Import louis after setting paths
import louis


class ContractionType(Enum):
    """UEB Contraction Types (following UEB rulebook sections 10.1-10.9)"""
    ALPHABETIC_WORDSIGN = auto()      # 10.1: Single letter representing whole word (but -> b)
    STRONG_WORDSIGN = auto()          # 10.2: Strong wordsigns (child, shall, this, etc.)
    STRONG_CONTRACTION = auto()       # 10.3: and, for, of, the, with
    STRONG_GROUPSIGN = auto()         # 10.4: ch, gh, sh, th, wh, ou, st, ar, ed, er, ing, ow
    LOWER_WORDSIGN = auto()           # 10.5: be, enough, were, his, in, was
    LOWER_GROUPSIGN = auto()          # 10.6: bb, be, cc, con, dis, ea, ff, gg, en, in
    INITIAL_LETTER_CONTRACTION = auto()  # 10.7: day, ever, father, here, etc.
    FINAL_LETTER_GROUPSIGN = auto()   # 10.8: ance, ence, ful, ity, less, ment, ness, etc.
    SHORTFORM = auto()                # 10.9: about, above, according, after, etc.
    UNKNOWN = auto()                  # Could not classify


@dataclass
class ContractionSpan:
    """Represents a single contraction found in the text."""
    print_start: int           # Start position in print text
    print_end: int             # End position in print text (exclusive)
    braille_start: int         # Start position in braille output
    braille_end: int           # End position in braille output (exclusive)
    print_text: str            # The contracted print text
    braille_text: str          # The braille representation
    braille_unicode: str       # Unicode braille representation
    contraction_type: ContractionType = ContractionType.UNKNOWN

    def to_dict(self):
        return {
            'printStart': self.print_start,
            'printEnd': self.print_end,
            'brailleStart': self.braille_start,
            'brailleEnd': self.braille_end,
            'printText': self.print_text,
            'brailleText': self.braille_text,
            'brailleUnicode': self.braille_unicode,
            'contractionType': self.contraction_type.name if self.contraction_type else None
        }


@dataclass
class TranslationResult:
    """Complete translation result with contraction information."""
    original_text: str
    braille_text: str
    braille_unicode: str
    contractions: list[ContractionSpan] = field(default_factory=list)

    def to_dict(self):
        return {
            'originalText': self.original_text,
            'brailleText': self.braille_text,
            'brailleUnicode': self.braille_unicode,
            'contractions': [c.to_dict() for c in self.contractions]
        }


# Known contractions database for classification
# Format: {braille_dots: (print_text, ContractionType)}
# Dots are represented as the braille unicode offset from 0x2800

ALPHABETIC_WORDSIGNS = {
    'but': ('b', 0x03),       # dots 12
    'can': ('c', 0x09),       # dots 14
    'do': ('d', 0x19),        # dots 145
    'every': ('e', 0x11),     # dots 15
    'from': ('f', 0x0B),      # dots 124
    'go': ('g', 0x1B),        # dots 1245
    'have': ('h', 0x13),      # dots 125
    'just': ('j', 0x2A),      # dots 245
    'knowledge': ('k', 0x05), # dots 13
    'like': ('l', 0x07),      # dots 123
    'more': ('m', 0x0D),      # dots 134
    'not': ('n', 0x1D),       # dots 1345
    'people': ('p', 0x0F),    # dots 1234
    'quite': ('q', 0x1F),     # dots 12345
    'rather': ('r', 0x17),    # dots 1235
    'so': ('s', 0x0E),        # dots 234
    'that': ('t', 0x1E),      # dots 2345
    'us': ('u', 0x25),        # dots 136
    'very': ('v', 0x27),      # dots 1236
    'will': ('w', 0x3A),      # dots 2456
    'it': ('x', 0x2D),        # dots 1346
    'you': ('y', 0x3D),       # dots 13456
    'as': ('z', 0x35),        # dots 1356
}

STRONG_WORDSIGNS = {
    'child': (0x21,),         # dots 16
    'shall': (0x29,),         # dots 146
    'this': (0x39,),          # dots 1456
    'which': (0x31,),         # dots 156
    'out': (0x36,),           # dots 1256
    'still': (0x0C,),         # dots 34
}

STRONG_CONTRACTIONS = {
    'and': (0x2F,),           # dots 12346
    'for': (0x3F,),           # dots 123456
    'of': (0x37,),            # dots 12356
    'the': (0x2E,),           # dots 2346
    'with': (0x3E,),          # dots 23456
}

STRONG_GROUPSIGNS = {
    'ch': (0x21,),            # dots 16
    'gh': (0x23,),            # dots 126
    'sh': (0x29,),            # dots 146
    'th': (0x39,),            # dots 1456
    'wh': (0x31,),            # dots 156
    'ou': (0x36,),            # dots 1256
    'st': (0x0C,),            # dots 34
    'ar': (0x1C,),            # dots 345
    'ed': (0x2B,),            # dots 1246
    'er': (0x3B,),            # dots 12456
    'ing': (0x2C,),           # dots 346
    'ow': (0x2A,),            # dots 246
}

LOWER_WORDSIGNS = {
    'be': (0x06,),            # dots 23
    'enough': (0x22,),        # dots 26
    'were': (0x36,),          # dots 2356
    'his': (0x26,),           # dots 236
    'in': (0x14,),            # dots 35
    'was': (0x1C,),           # dots 356
}

# Lower groupsigns (Section 10.6)
LOWER_GROUPSIGNS = {
    'bb', 'be', 'cc', 'con', 'dis', 'ea', 'ff', 'gg', 'en', 'in'
}

# Initial-letter contractions (Section 10.7)
INITIAL_LETTER_CONTRACTIONS = {
    'day', 'ever', 'father', 'here', 'know', 'lord', 'mother', 'name',
    'one', 'part', 'question', 'right', 'some', 'time', 'under', 'work',
    'young', 'there', 'these', 'those', 'upon', 'word', 'whose', 'cannot',
    'many', 'spirit', 'their', 'world', 'character', 'through', 'where',
    'ought', 'could', 'would', 'should', 'much', 'such'
}

# Final-letter groupsigns (Section 10.8)
FINAL_LETTER_GROUPSIGNS = {
    'ound', 'ance', 'sion', 'less', 'ount', 'ence', 'tion', 'ness',
    'ment', 'ful', 'ity', 'ong'
}

# Shortforms (Section 10.9)
SHORTFORMS = {
    'about', 'above', 'according', 'across', 'after', 'afternoon', 'afterward',
    'again', 'against', 'almost', 'already', 'also', 'although', 'altogether',
    'always', 'because', 'before', 'behind', 'below', 'beneath', 'beside',
    'between', 'beyond', 'blind', 'braille', 'children', 'conceive', 'could',
    'deceive', 'declare', 'either', 'first', 'friend', 'good', 'great',
    'herself', 'him', 'himself', 'immediate', 'its', 'itself', 'letter',
    'little', 'much', 'must', 'myself', 'necessary', 'neither', 'oneself',
    'ourselves', 'paid', 'perceive', 'perhaps', 'quick', 'receive', 'rejoice',
    'said', 'should', 'such', 'themselves', 'thyself', 'today', 'together',
    'tomorrow', 'tonight', 'would', 'your', 'yourself', 'yourselves'
}

# Build a lookup for quick contraction classification
def build_contraction_lookup():
    """Build a lookup table for classifying contractions."""
    lookup = {}

    for word, (letter, dots) in ALPHABETIC_WORDSIGNS.items():
        lookup[word.lower()] = ContractionType.ALPHABETIC_WORDSIGN

    for word in STRONG_WORDSIGNS:
        lookup[word.lower()] = ContractionType.STRONG_WORDSIGN

    for word in STRONG_CONTRACTIONS:
        lookup[word.lower()] = ContractionType.STRONG_CONTRACTION

    for group in STRONG_GROUPSIGNS:
        lookup[group.lower()] = ContractionType.STRONG_GROUPSIGN

    for word in LOWER_WORDSIGNS:
        lookup[word.lower()] = ContractionType.LOWER_WORDSIGN

    for group in LOWER_GROUPSIGNS:
        lookup[group.lower()] = ContractionType.LOWER_GROUPSIGN

    for word in INITIAL_LETTER_CONTRACTIONS:
        lookup[word.lower()] = ContractionType.INITIAL_LETTER_CONTRACTION

    for group in FINAL_LETTER_GROUPSIGNS:
        lookup[group.lower()] = ContractionType.FINAL_LETTER_GROUPSIGN

    for word in SHORTFORMS:
        lookup[word.lower()] = ContractionType.SHORTFORM

    return lookup

CONTRACTION_LOOKUP = build_contraction_lookup()


# =============================================================================
# BRAILLE CHARACTER DETECTION HELPERS
# =============================================================================
#
# CRITICAL: THE ALGORITHM MUST RUN ON ASCII BRAILLE, NOT UNICODE BRAILLE!
#
# Why? In ASCII braille (from liblouis):
#   - Letter 'e' is ASCII 'e'
#   - "en" contraction is ASCII '5'
#   - They are DIFFERENT characters, so we can distinguish them
#
# In Unicode braille:
#   - Letter 'e' is U+2811 (dots 1,5)
#   - "en" contraction is ALSO U+2811 (same dot pattern!)
#   - They are THE SAME character - we CANNOT distinguish them!
#
# This is because braille dot patterns are context-dependent. The same pattern
# can mean a letter OR a contraction depending on the word. Only by comparing
# the contracted (G2) output with the uncontracted (G1) output using ASCII
# characters can we determine which cells are standalone letters vs contractions.
#
# SWIFT PORT WORKFLOW:
#   1. Get ASCII braille + inputPos from liblouis (don't convert to Unicode yet!)
#   2. Run contraction detection algorithm on ASCII braille
#   3. THEN convert ASCII braille to Unicode for display
#   4. Use the contraction indices to highlight the Unicode display
#
# The helpers below work with ASCII braille from liblouis.

# Unicode braille code points for letters a-z
BRAILLE_LETTER_UNICODE = frozenset([
    '\u2801',  # a - dots 1
    '\u2803',  # b - dots 12
    '\u2809',  # c - dots 14
    '\u2819',  # d - dots 145
    '\u2811',  # e - dots 15
    '\u280b',  # f - dots 124
    '\u281b',  # g - dots 1245
    '\u2813',  # h - dots 125
    '\u280a',  # i - dots 24
    '\u281a',  # j - dots 245
    '\u2805',  # k - dots 13
    '\u2807',  # l - dots 123
    '\u280d',  # m - dots 134
    '\u281d',  # n - dots 1345
    '\u2815',  # o - dots 135
    '\u280f',  # p - dots 1234
    '\u281f',  # q - dots 12345
    '\u2817',  # r - dots 1235
    '\u280e',  # s - dots 234
    '\u281e',  # t - dots 2345
    '\u2825',  # u - dots 136
    '\u2827',  # v - dots 1236
    '\u283a',  # w - dots 2456
    '\u282d',  # x - dots 1346
    '\u283d',  # y - dots 13456
    '\u2835',  # z - dots 1356
])

# ASCII braille letters (for liblouis output)
ASCII_BRAILLE_LETTERS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')

# Capital indicator in ASCII braille
ASCII_CAPITAL_INDICATOR = ','


def is_braille_letter(char: str) -> bool:
    """
    Check if an ASCII braille character represents a letter (a-z).

    IMPORTANT: This function is designed for ASCII braille from liblouis.
    Using it on Unicode braille will give INCORRECT results because the same
    Unicode character (e.g., U+2811) can represent both a letter AND a contraction.

    For Swift ports: Replace isalpha()/isLetter with this function, but make sure
    you're working with ASCII braille strings, not Unicode braille.

    Args:
        char: A single ASCII braille character from liblouis

    Returns:
        True if the character is an ASCII letter (a-z, A-Z)
    """
    if not char:
        return False

    # Only check ASCII braille letters - this is the only reliable way
    # DO NOT check Unicode braille because the same code point can be
    # either a letter or a contraction (e.g., U+2811 = 'e' OR 'en')
    return char in ASCII_BRAILLE_LETTERS


def is_capital_indicator(char: str) -> bool:
    """
    Check if a braille character is a capital indicator.
    Works with both ASCII braille and Unicode braille.

    Args:
        char: A single braille character (ASCII or Unicode)

    Returns:
        True if the character is a capital indicator
    """
    if not char:
        return False

    # ASCII capital indicator
    if char == ',':
        return True

    # Unicode capital indicator (dots 6)
    if char == '\u2820':
        return True

    return False


def get_tables_path():
    """Get the path to liblouis tables."""
    return os.path.join(os.path.dirname(__file__), 'tables')


def dots_to_unicode(dots_str: str) -> str:
    """Convert liblouis ASCII braille to unicode braille."""
    # liblouis uses North American Braille ASCII (NABCC)
    # Map from ASCII to Unicode braille
    ASCII_TO_UNICODE = {
        ' ': '\u2800',  # blank
        'a': '\u2801', 'b': '\u2803', 'c': '\u2809', 'd': '\u2819', 'e': '\u2811',
        'f': '\u280b', 'g': '\u281b', 'h': '\u2813', 'i': '\u280a', 'j': '\u281a',
        'k': '\u2805', 'l': '\u2807', 'm': '\u280d', 'n': '\u281d', 'o': '\u2815',
        'p': '\u280f', 'q': '\u281f', 'r': '\u2817', 's': '\u280e', 't': '\u281e',
        'u': '\u2825', 'v': '\u2827', 'w': '\u283a', 'x': '\u282d', 'y': '\u283d',
        'z': '\u2835',
        '1': '\u2801', '2': '\u2803', '3': '\u2809', '4': '\u2819', '5': '\u2811',
        '6': '\u280b', '7': '\u281b', '8': '\u2813', '9': '\u280a', '0': '\u281a',
        ',': '\u2802',  # dots 2
        ';': '\u2806',  # dots 23
        ':': '\u2812',  # dots 25
        '.': '\u2832',  # dots 256
        '!': '\u282e',  # dots 2346 (the)
        '?': '\u2839',  # dots 1456 (this)
        '"': '\u2810',  # dots 5
        "'": '\u2804',  # dots 3
        '-': '\u2824',  # dots 36
        '/': '\u280c',  # dots 34 (st)
        '(': '\u2836',  # dots 2356
        ')': '\u283e',  # dots 23456 (with)
        '*': '\u2821',  # dots 16 (ch/child)
        '&': '\u282f',  # dots 12346 (and)
        '%': '\u283c',  # dots 3456
        '#': '\u283c',  # dots 3456 (number sign)
        '@': '\u2800',  # placeholder
        '[': '\u282a',  # dots 246 (ow)
        ']': '\u283b',  # dots 12456 (er)
        '{': '\u282a',  # dots 246 (ow)
        '}': '\u283b',  # dots 12456 (er)
        '<': '\u2823',  # dots 126 (gh)
        '>': '\u281c',  # dots 345 (ar)
        '=': '\u283f',  # dots 123456 (for)
        '+': '\u282c',  # dots 346 (ing)
        '_': '\u2838',  # dots 456
        '$': '\u282b',  # dots 1246 (ed)
        '|': '\u2836',  # dots 1256 (ou)
    }

    result = []
    for char in dots_str:
        code = ord(char)
        # If it's already in the braille unicode range
        if 0x2800 <= code <= 0x28FF:
            result.append(char)
        elif char.lower() in ASCII_TO_UNICODE:
            result.append(ASCII_TO_UNICODE[char.lower()])
        else:
            result.append(char)
    return ''.join(result)


def translate_g1(text: str) -> tuple[str, list[int], list[int]]:
    """Translate text using Grade 1 (uncontracted) UEB."""
    tables = [os.path.join(get_tables_path(), 'en-ueb-g1.ctb')]
    braille, input_pos, output_pos, cursor = louis.translate(tables, text, mode=0)
    return braille, list(input_pos), list(output_pos)


def translate_g2(text: str) -> tuple[str, list[int], list[int]]:
    """Translate text using Grade 2 (contracted) UEB."""
    tables = [os.path.join(get_tables_path(), 'en-ueb-g2.ctb')]
    braille, input_pos, output_pos, cursor = louis.translate(tables, text, mode=0)
    return braille, list(input_pos), list(output_pos)


def translate_g2_with_mode(text: str, mode: int = 0) -> tuple[str, list[int], list[int]]:
    """Translate text using Grade 2 with specific mode."""
    tables = [os.path.join(get_tables_path(), 'en-ueb-g2.ctb')]
    braille, input_pos, output_pos, cursor = louis.translate(tables, text, mode=mode)
    return braille, list(input_pos), list(output_pos)


def is_indicator(char: str, context_braille: str, pos: int) -> bool:
    """
    Check if a braille cell is an indicator (not a contraction).

    Indicators include:
    - Capital letter indicator: dots 6 (0x20)
    - Capital word indicator: dots 6-6
    - Capital passage indicator: dots 6-6-6
    - Number sign: dots 3456 (0x3C)
    - Grade 1 indicator: dots 56 (0x30)
    - Emphasis indicators: various

    This function handles both Unicode braille and ASCII braille (NABCC).
    """
    code = ord(char)

    # =========================================
    # ASCII Braille (NABCC) indicators
    # =========================================

    # Dots 6 - capital letter indicator (ASCII: ',')
    # This is the most common indicator that appears before contractions
    if char == ',':
        return True

    # Dots 3456 - number sign (ASCII: '#')
    if char == '#':
        return True

    # NOTE: We do NOT treat ';' (dots 56) as an indicator here because
    # in the context of contractions, ';' is the final-letter groupsign
    # prefix (e.g., ';n' for -tion, ';s' for -ness) and IS part of the
    # contraction. The letter sign use of ';' would not appear at the
    # start of a contraction span.

    # NOTE: We do NOT treat '.' (dots 46) as an indicator because it's
    # also used for punctuation and as part of contractions (.s for -less)

    # Dots 456 - underline, some emphasis (ASCII: '_')
    if char == '_':
        return True

    # Dots 45 - bold indicator prefix (ASCII: '^')
    if char == '^':
        return True

    # =========================================
    # Unicode Braille indicators
    # =========================================

    # Dots 6 alone - capital letter indicator
    if code == 0x2820:
        return True

    # Dots 3456 - number sign
    if code == 0x283C:
        return True

    # Dots 56 - grade 1 indicator / letter sign
    if code == 0x2830:
        return True

    # Dots 46 - various indicators (italic letter, final-letter prefix)
    if code == 0x2828:
        return True

    # Dots 456 - underline, some emphasis
    if code == 0x2838:
        return True

    # Dots 45 - bold indicator prefix
    if code == 0x2818:
        return True

    # Dots 5 - various prefixes (initial-letter prefix)
    if code == 0x2810:
        return True

    return False


def classify_contraction(print_text: str, braille_len: int) -> ContractionType:
    """
    Attempt to classify a contraction based on the print text.
    """
    lower_text = print_text.lower()

    # Check exact matches in known contractions
    if lower_text in CONTRACTION_LOOKUP:
        return CONTRACTION_LOOKUP[lower_text]

    # Check if text contains a strong groupsign
    for group in STRONG_GROUPSIGNS:
        if group in lower_text:
            return ContractionType.STRONG_GROUPSIGN

    # Check if text contains a lower groupsign
    for group in LOWER_GROUPSIGNS:
        if group in lower_text:
            return ContractionType.LOWER_GROUPSIGN

    # Check if text ends with a final-letter groupsign
    for group in FINAL_LETTER_GROUPSIGNS:
        if lower_text.endswith(group):
            return ContractionType.FINAL_LETTER_GROUPSIGN

    # Check if it's a known shortform
    for shortform in SHORTFORMS:
        if lower_text == shortform or lower_text.startswith(shortform):
            return ContractionType.SHORTFORM

    return ContractionType.UNKNOWN


def detect_contractions(text: str) -> TranslationResult:
    """
    Detect contractions in text by comparing G1 and G2 translations.

    Algorithm:
    1. Translate with G1 (uncontracted) to get baseline
    2. Translate with G2 (contracted) to get contracted output
    3. Compare position mappings to find where contractions occurred
    4. For each contraction, extract the print span and braille span
    5. Filter out indicators (capitals, numbers, etc.)
    6. Attempt to classify each contraction

    Returns:
        TranslationResult with all detected contractions
    """
    if not text:
        return TranslationResult(
            original_text=text,
            braille_text='',
            braille_unicode='',
            contractions=[]
        )

    # Get both translations
    g1_braille, g1_input_pos, g1_output_pos = translate_g1(text)
    g2_braille, g2_input_pos, g2_output_pos = translate_g2(text)

    contractions = []

    # Convert g2_output_pos to a more useful format
    # g2_output_pos[i] tells us where print character i starts in the braille output

    # Find contraction boundaries by looking for "compression" in the mapping
    # When multiple print characters map to the same or fewer braille cells in G2
    # compared to G1, a contraction has occurred

    i = 0
    while i < len(text):
        # Find where this character maps to in both G1 and G2
        g1_pos = g1_output_pos[i] if i < len(g1_output_pos) else len(g1_braille)
        g2_pos = g2_output_pos[i] if i < len(g2_output_pos) else len(g2_braille)

        # Look ahead to find the end of this "unit" (where next different mapping starts)
        j = i + 1
        while j < len(text):
            next_g1_pos = g1_output_pos[j] if j < len(g1_output_pos) else len(g1_braille)
            next_g2_pos = g2_output_pos[j] if j < len(g2_output_pos) else len(g2_braille)

            # Check if we've moved to a new braille cell in G2
            if next_g2_pos != g2_pos:
                break
            j += 1

        # Calculate braille cell counts for this print segment
        g1_start = g1_pos
        g1_end = g1_output_pos[j] if j < len(g1_output_pos) else len(g1_braille)
        g2_start = g2_pos
        g2_end = g2_output_pos[j] if j < len(g2_output_pos) else len(g2_braille)

        g1_cells = g1_end - g1_start
        g2_cells = g2_end - g2_start

        print_segment = text[i:j]
        braille_segment = g2_braille[g2_start:g2_end]

        # A contraction occurred if:
        # 1. G2 uses fewer cells than G1, AND
        # 2. The braille is not just an indicator
        # 3. The print segment is not whitespace or punctuation only

        is_contraction = False

        if g2_cells < g1_cells and print_segment.strip() and any(c.isalpha() for c in print_segment):
            # Check if the braille cells are indicators
            has_non_indicator = False
            for k, cell in enumerate(braille_segment):
                if not is_indicator(cell, braille_segment, k):
                    has_non_indicator = True
                    break

            if has_non_indicator:
                is_contraction = True

        if is_contraction:
            contraction = ContractionSpan(
                print_start=i,
                print_end=j,
                braille_start=g2_start,
                braille_end=g2_end,
                print_text=print_segment,
                braille_text=braille_segment,
                braille_unicode=braille_segment,  # Already unicode from louis
                contraction_type=classify_contraction(print_segment, g2_cells)
            )
            contractions.append(contraction)

        i = j

    return TranslationResult(
        original_text=text,
        braille_text=g2_braille,
        braille_unicode=dots_to_unicode(g2_braille),
        contractions=contractions
    )


def detect_contractions_detailed(text: str) -> TranslationResult:
    """
    Contraction detection using inputPos grouping and G1/G2 comparison.

    Algorithm:
    1. Translate text to G1 (uncontracted) and G2 (contracted)
    2. Group G2 braille by consecutive inputPos values
    3. For each group, compare to G1 to find standalone letters vs contractions
    4. Standalone letters match between G1 and G2; everything else is contracted
    5. Exclude capital indicators from braille spans
    """
    if not text:
        return TranslationResult(
            original_text=text,
            braille_text='',
            braille_unicode='',
            contractions=[]
        )

    # Get G2 translation with position mapping
    g2_braille, g2_input_pos, g2_output_pos = translate_g2(text)

    # Get G1 translation for comparison
    g1_braille, g1_input_pos, g1_output_pos = translate_g1(text)

    contractions = []
    processed_print_ranges = set()

    if not g2_braille or not g2_input_pos:
        return TranslationResult(
            original_text=text,
            braille_text=g2_braille,
            braille_unicode=dots_to_unicode(g2_braille),
            contractions=[]
        )

    # Group consecutive braille characters by their inputPos value
    groups = []  # Each: (braille_start, braille_end, input_start)
    j = 0
    while j < len(g2_braille):
        braille_start = j
        input_start = g2_input_pos[j]

        # Extend group while inputPos stays the same
        while j + 1 < len(g2_braille) and g2_input_pos[j + 1] == input_start:
            j += 1

        braille_end = j + 1
        groups.append((braille_start, braille_end, input_start))
        j += 1

    # Process each group to find contractions
    for idx, (braille_start, braille_end, input_start) in enumerate(groups):
        # Find where the input span ends (start of next group, or end of text)
        if idx + 1 < len(groups):
            input_end = groups[idx + 1][2]
        else:
            input_end = len(text)

        input_text = text[input_start:input_end]
        input_len = input_end - input_start
        braille_len = braille_end - braille_start

        # Skip if this is just whitespace or punctuation
        if not any(c.isalpha() for c in input_text):
            continue

        # Skip leading capital indicators in braille
        braille_content_start = braille_start
        while braille_content_start < braille_end and is_capital_indicator(g2_braille[braille_content_start]):
            braille_content_start += 1

        braille_content_len = braille_end - braille_content_start
        if braille_content_len <= 0:
            continue

        # Check compression against CONTENT length (excluding indicators)
        if input_len <= braille_content_len:
            continue

        braille_content = g2_braille[braille_content_start:braille_end]

        # Case 1: Single braille content char represents multiple input chars
        # This is a wordsign - the whole input is contracted to one symbol
        if braille_content_len == 1:
            contraction_input_start = input_start
            contraction_input_end = input_end
            contraction_braille_start = braille_content_start
            contraction_braille_end = braille_end

        # Case 2: Braille content is entirely letter patterns AND matches G1
        # This means it's a true shortform (e.g., "together" -> "tgr", "about" -> "ab")
        # BUT: We must verify G2 doesn't match G1, otherwise letters like 'x' might
        # actually be wordsigns (e.g., "its" -> "xs" where 'x' = "it" wordsign)
        elif all(is_braille_letter(c) for c in braille_content):
            # Get corresponding G1 content to verify it's truly a shortform
            g1_pos = None
            for k, inp in enumerate(g1_input_pos):
                if inp == input_start:
                    g1_pos = k
                    break

            # Check if G2 content matches G1 - if so, no contraction
            g1_segment = ""
            if g1_pos is not None:
                # Extract G1 segment for this input range
                g1_end = g1_pos
                while g1_end < len(g1_input_pos) and g1_input_pos[g1_end] < input_end:
                    g1_end += 1
                g1_segment = g1_braille[g1_pos:g1_end]

            # If G2 matches G1, skip (no contraction) or fall through to Case 3
            if braille_content == g1_segment:
                # No contraction - G2 matches G1
                continue
            elif g1_pos is not None and len(braille_content) < len(g1_segment):
                # G2 is shorter than G1 - check if some letters match (Case 3 logic)
                # This handles cases like "its" -> "xs" where 'x'="it" but 's'='s'
                g2_pos = braille_content_start
                g1_curr = g1_pos

                # Skip non-letter indicators in G1
                while g1_curr < len(g1_braille) and not is_braille_letter(g1_braille[g1_curr]):
                    g1_curr += 1

                input_consumed = input_start
                if g1_curr < len(g1_input_pos):
                    input_consumed = g1_input_pos[g1_curr]

                # Find matching standalone letters from the END (since wordsigns are often at start)
                # Actually, compare from start to find where contraction ends
                matched_letters_end_g2 = braille_content_start
                temp_g1 = g1_curr
                temp_g2 = braille_content_start

                # First, try matching from start
                while temp_g2 < braille_end and temp_g1 < len(g1_braille):
                    if g2_braille[temp_g2] == g1_braille[temp_g1] and is_braille_letter(g2_braille[temp_g2]):
                        temp_g2 += 1
                        temp_g1 += 1
                    else:
                        break

                # If nothing matched from start, the contraction is at the beginning
                # Find matching letters from END
                matched_from_end_g2 = braille_end
                # NOTE: Must use "is not None" because g1_pos=0 is valid but falsy
                matched_from_end_g1 = len(g1_segment) + g1_pos if g1_pos is not None else len(g1_braille)

                while matched_from_end_g2 > braille_content_start and matched_from_end_g1 > g1_curr:
                    g2_char = g2_braille[matched_from_end_g2 - 1]
                    g1_char = g1_braille[matched_from_end_g1 - 1] if matched_from_end_g1 <= len(g1_braille) else ''
                    if g2_char == g1_char and is_braille_letter(g2_char):
                        matched_from_end_g2 -= 1
                        matched_from_end_g1 -= 1
                    else:
                        break

                # The contraction is from start to where end-matching began
                contraction_braille_start = braille_content_start
                contraction_braille_end = matched_from_end_g2

                # Calculate input positions
                contraction_input_start = input_start
                # Count how many G1 chars are consumed by the contraction
                # NOTE: Must use "is not None" because g1_pos=0 is valid but falsy
                g1_chars_in_contraction = (matched_from_end_g1 - g1_curr) if g1_pos is not None else input_len
                contraction_input_end = input_start + g1_chars_in_contraction

                if contraction_braille_start >= contraction_braille_end:
                    continue
                if contraction_input_start >= contraction_input_end:
                    continue

                # VALIDATION: Verify the split by translating the contracted portion alone
                # For "its" -> "xs", translating "it" should give "x" (wordsign)
                # For "could" -> "cd", translating "coul" gives "c|l" not "c" (invalid split)
                contracted_text = text[contraction_input_start:contraction_input_end]
                expected_braille = g2_braille[contraction_braille_start:contraction_braille_end]
                actual_braille, _, _ = translate_g2(contracted_text)

                if actual_braille != expected_braille:
                    # Invalid split - the contracted portion doesn't translate to expected braille
                    # Fall through to treat whole word as shortform
                    contraction_input_start = input_start
                    contraction_input_end = input_end
                    contraction_braille_start = braille_content_start
                    contraction_braille_end = braille_end
            else:
                # True shortform - whole thing is contracted
                contraction_input_start = input_start
                contraction_input_end = input_end
                contraction_braille_start = braille_content_start
                contraction_braille_end = braille_end

        else:
            # Case 3: Mixed content with non-alpha symbols (groupsigns like ">", "?", "+")
            # Find standalone letters by comparing to G1
            g1_pos = None
            for k, inp in enumerate(g1_input_pos):
                if inp == input_start:
                    g1_pos = k
                    break

            if g1_pos is None:
                if input_start < len(g1_output_pos):
                    g1_pos = g1_output_pos[input_start]
                else:
                    continue

            # Compare G2 group to G1 starting at g1_pos
            g2_pos = braille_content_start
            g1_curr = g1_pos

            # Skip matching leading indicators in G1 as well
            # NOTE: Uses is_braille_letter() instead of isalpha() to work with Unicode braille
            while (g1_curr < len(g1_braille) and not is_braille_letter(g1_braille[g1_curr])):
                g1_curr += 1

            # Track how much of the input we've "consumed" with matched letters
            input_consumed = input_start
            if g1_curr < len(g1_input_pos):
                input_consumed = g1_input_pos[g1_curr]

            # Find matching standalone letters
            matched_letters_end_g2 = g2_pos
            while (matched_letters_end_g2 < braille_end and g1_curr < len(g1_braille)):
                g2_char = g2_braille[matched_letters_end_g2]
                g1_char = g1_braille[g1_curr]

                # Match only if both are the same letter pattern
                # NOTE: Uses is_braille_letter() instead of isalpha() to work with Unicode braille
                if g2_char == g1_char and is_braille_letter(g2_char):
                    matched_letters_end_g2 += 1
                    g1_curr += 1
                    if g1_curr < len(g1_input_pos):
                        input_consumed = g1_input_pos[g1_curr]
                    else:
                        input_consumed = input_end
                else:
                    break

            # The contraction is from matched_letters_end_g2 to braille_end
            contraction_braille_start = matched_letters_end_g2
            contraction_braille_end = braille_end
            contraction_input_start = input_consumed
            contraction_input_end = input_end

            # Skip if no actual contraction found
            if contraction_input_start >= contraction_input_end:
                continue
            if contraction_braille_start >= contraction_braille_end:
                continue

        contraction_input_text = text[contraction_input_start:contraction_input_end]
        contraction_braille_text = g2_braille[contraction_braille_start:contraction_braille_end]

        # Skip if input is not alphabetic
        if not any(c.isalpha() for c in contraction_input_text):
            continue

        c_input_len = contraction_input_end - contraction_input_start
        c_braille_len = contraction_braille_end - contraction_braille_start

        # It's a contraction if more input chars than braille chars
        if c_input_len > c_braille_len:
            print_range = (contraction_input_start, contraction_input_end)
            if print_range not in processed_print_ranges:
                contraction = ContractionSpan(
                    print_start=contraction_input_start,
                    print_end=contraction_input_end,
                    braille_start=contraction_braille_start,
                    braille_end=contraction_braille_end,
                    print_text=contraction_input_text,
                    braille_text=contraction_braille_text,
                    braille_unicode=dots_to_unicode(contraction_braille_text),
                    contraction_type=classify_contraction(contraction_input_text, c_braille_len)
                )
                contractions.append(contraction)
                processed_print_ranges.add(print_range)

    return TranslationResult(
        original_text=text,
        braille_text=g2_braille,
        braille_unicode=dots_to_unicode(g2_braille),
        contractions=contractions
    )


# ============================================================================
# COMPREHENSIVE TEST SUITE WITH EXACT EXPECTED VALUES
# ============================================================================

def run_tests():
    """
    Run comprehensive test suite for contraction detection.

    Each test case has exact expected values for:
    - input: The input text
    - expected_braille: The expected braille output (ASCII)
    - expected_contractions: List of tuples with exact values:
      (print_start, print_end, braille_start, braille_end, print_text, braille_text, contraction_type)
    """

    print("=" * 70)
    print("CONTRACTION DETECTION TEST SUITE (EXACT VALUES)")
    print("=" * 70)

    # Each contraction tuple: (print_start, print_end, braille_start, braille_end, print_text, braille_text, type)
    test_cases = [
        # =====================================================================
        # BASIC ALPHABETIC WORDSIGNS (Section 10.1)
        # =====================================================================
        {
            'name': 'Alphabetic wordsign: but',
            'input': 'but',
            'expected_braille': 'b',
            'expected_contractions': [
                (0, 3, 0, 1, 'but', 'b', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: can',
            'input': 'can',
            'expected_braille': 'c',
            'expected_contractions': [
                (0, 3, 0, 1, 'can', 'c', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: do',
            'input': 'do',
            'expected_braille': 'd',
            'expected_contractions': [
                (0, 2, 0, 1, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: every',
            'input': 'every',
            'expected_braille': 'e',
            'expected_contractions': [
                (0, 5, 0, 1, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: just',
            'input': 'just',
            'expected_braille': 'j',
            'expected_contractions': [
                (0, 4, 0, 1, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: you',
            'input': 'you',
            'expected_braille': 'y',
            'expected_contractions': [
                (0, 3, 0, 1, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: will',
            'input': 'will',
            'expected_braille': 'w',
            'expected_contractions': [
                (0, 4, 0, 1, 'will', 'w', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Alphabetic wordsign: it',
            'input': 'it',
            'expected_braille': 'x',
            'expected_contractions': [
                (0, 2, 0, 1, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # STRONG WORDSIGNS (Section 10.2)
        # =====================================================================
        {
            'name': 'Strong wordsign: child',
            'input': 'child',
            'expected_braille': '*',
            'expected_contractions': [
                (0, 5, 0, 1, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Strong wordsign: shall',
            'input': 'shall',
            'expected_braille': '%',
            'expected_contractions': [
                (0, 5, 0, 1, 'shall', '%', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Strong wordsign: this',
            'input': 'this',
            'expected_braille': '?',
            'expected_contractions': [
                (0, 4, 0, 1, 'this', '?', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Strong wordsign: which',
            'input': 'which',
            'expected_braille': ':',
            'expected_contractions': [
                (0, 5, 0, 1, 'which', ':', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Strong wordsign: out',
            'input': 'out',
            'expected_braille': '|',
            'expected_contractions': [
                (0, 3, 0, 1, 'out', '|', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Strong wordsign: still',
            'input': 'still',
            'expected_braille': '/',
            'expected_contractions': [
                (0, 5, 0, 1, 'still', '/', 'STRONG_WORDSIGN'),
            ],
        },

        # =====================================================================
        # STRONG CONTRACTIONS (Section 10.3)
        # =====================================================================
        {
            'name': 'Strong contraction: and',
            'input': 'and',
            'expected_braille': '&',
            'expected_contractions': [
                (0, 3, 0, 1, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Strong contraction: for',
            'input': 'for',
            'expected_braille': '=',
            'expected_contractions': [
                (0, 3, 0, 1, 'for', '=', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Strong contraction: of',
            'input': 'of',
            'expected_braille': '(',
            'expected_contractions': [
                (0, 2, 0, 1, 'of', '(', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Strong contraction: the',
            'input': 'the',
            'expected_braille': '!',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Strong contraction: with',
            'input': 'with',
            'expected_braille': ')',
            'expected_contractions': [
                (0, 4, 0, 1, 'with', ')', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # STRONG GROUPSIGNS (Section 10.4)
        # =====================================================================
        {
            'name': 'Strong groupsign: ch in church',
            'input': 'church',
            'expected_braille': '*ur*',
            'expected_contractions': [
                (0, 2, 0, 1, 'ch', '*', 'STRONG_GROUPSIGN'),
                (4, 6, 3, 4, 'ch', '*', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Strong groupsign: sh in she',
            'input': 'she',
            'expected_braille': '%e',
            'expected_contractions': [
                (0, 2, 0, 1, 'sh', '%', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Strong groupsign: th+ing in thing',
            'input': 'thing',
            'expected_braille': '?+',
            'expected_contractions': [
                (0, 2, 0, 1, 'th', '?', 'STRONG_GROUPSIGN'),
                (2, 5, 1, 2, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Strong groupsign: ing in going',
            'input': 'going',
            'expected_braille': 'go+',
            'expected_contractions': [
                (2, 5, 2, 3, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Initial-letter: mother',
            'input': 'mother',
            'expected_braille': '"m',
            'expected_contractions': [
                (0, 6, 0, 2, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Strong groupsign: ed in walked',
            'input': 'walked',
            'expected_braille': 'walk$',
            'expected_contractions': [
                (4, 6, 4, 5, 'ed', '$', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # SENTENCES WITH MULTIPLE CONTRACTIONS
        # =====================================================================
        {
            'name': 'Sentence: the child will go',
            'input': 'the child will go',
            'expected_braille': '! * w g',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 9, 2, 3, 'child', '*', 'STRONG_WORDSIGN'),
                (10, 14, 4, 5, 'will', 'w', 'ALPHABETIC_WORDSIGN'),
                (15, 17, 6, 7, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Sentence: I can do it',
            'input': 'I can do it',
            'expected_braille': ',i c d x',
            'expected_contractions': [
                (2, 5, 3, 4, 'can', 'c', 'ALPHABETIC_WORDSIGN'),
                (6, 8, 5, 6, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (9, 11, 7, 8, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Sentence: this and that',
            'input': 'this and that',
            'expected_braille': '? & t',
            'expected_contractions': [
                (0, 4, 0, 1, 'this', '?', 'STRONG_WORDSIGN'),
                (5, 8, 2, 3, 'and', '&', 'STRONG_CONTRACTION'),
                (9, 13, 4, 5, 'that', 't', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Sentence: with every child',
            'input': 'with every child',
            'expected_braille': ') e *',
            'expected_contractions': [
                (0, 4, 0, 1, 'with', ')', 'STRONG_CONTRACTION'),
                (5, 10, 2, 3, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (11, 16, 4, 5, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },

        # =====================================================================
        # WORDS WITH MULTIPLE GROUPSIGNS
        # =====================================================================
        {
            'name': 'Word: brother (contains "the")',
            'input': 'brother',
            'expected_braille': 'bro!r',
            'expected_contractions': [
                (3, 6, 3, 4, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: everything',
            'input': 'everything',
            'expected_braille': '"ey?+',
            'expected_contractions': [
                (0, 4, 0, 2, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (5, 7, 3, 4, 'th', '?', 'STRONG_GROUPSIGN'),
                (7, 10, 4, 5, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Shortform: together',
            'input': 'together',
            'expected_braille': 'tgr',
            'expected_contractions': [
                (0, 8, 0, 3, 'together', 'tgr', 'SHORTFORM'),
            ],
        },

        # =====================================================================
        # CAPITALIZATION
        # =====================================================================
        {
            'name': 'Capital: The',
            'input': 'The',
            'expected_braille': ',!',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'All caps: AND',
            'input': 'AND',
            'expected_braille': ',,&',
            'expected_contractions': [
                (0, 3, 2, 3, 'AND', '&', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # NUMBERS (should NOT produce contractions)
        # =====================================================================
        {
            'name': 'Number: 123',
            'input': '123',
            'expected_braille': '#abc',
            'expected_contractions': [],
        },
        {
            'name': 'Number with text: room 123',
            'input': 'room 123',
            'expected_braille': 'room #abc',
            'expected_contractions': [],
        },

        # =====================================================================
        # PUNCTUATION
        # =====================================================================
        {
            'name': 'Quoted: "the"',
            'input': '"the"',
            'expected_braille': '8!0',
            'expected_contractions': [
                (1, 4, 1, 2, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # EMPTY AND EDGE CASES
        # =====================================================================
        {
            'name': 'Empty string',
            'input': '',
            'expected_braille': '',
            'expected_contractions': [],
        },
        {
            'name': 'Single space',
            'input': ' ',
            'expected_braille': ' ',
            'expected_contractions': [],
        },
        {
            'name': 'Single letter: a',
            'input': 'a',
            'expected_braille': 'a',
            'expected_contractions': [],
        },
        {
            'name': 'Single letter: I',
            'input': 'I',
            'expected_braille': ',i',
            'expected_contractions': [],
        },

        # =====================================================================
        # SHORTFORMS (Section 10.9)
        # =====================================================================
        {
            'name': 'Shortform: about',
            'input': 'about',
            'expected_braille': 'ab',
            'expected_contractions': [
                (0, 5, 0, 2, 'about', 'ab', 'SHORTFORM'),
            ],
        },
        {
            'name': 'Shortform: because',
            'input': 'because',
            'expected_braille': '2c',
            'expected_contractions': [
                (0, 7, 0, 2, 'because', '2c', 'SHORTFORM'),
            ],
        },
        {
            'name': 'Shortform: could',
            'input': 'could',
            'expected_braille': 'cd',
            'expected_contractions': [
                (0, 5, 0, 2, 'could', 'cd', 'SHORTFORM'),
            ],
        },
        {
            'name': 'Shortform: friend',
            'input': 'friend',
            'expected_braille': 'fr',
            'expected_contractions': [
                (0, 6, 0, 2, 'friend', 'fr', 'SHORTFORM'),
            ],
        },

        # =====================================================================
        # APOSTROPHES
        # =====================================================================
        {
            'name': "Apostrophe: it's",
            'input': "it's",
            'expected_braille': "x's",
            'expected_contractions': [
                (0, 2, 0, 1, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': "Apostrophe: can't",
            'input': "can't",
            'expected_braille': "c't",
            'expected_contractions': [
                (0, 3, 0, 1, 'can', 'c', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': "Apostrophe: you're",
            'input': "you're",
            'expected_braille': "y're",
            'expected_contractions': [
                (0, 3, 0, 1, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # INITIAL-LETTER CONTRACTIONS (Section 10.7)
        # =====================================================================
        {
            'name': 'Initial-letter: day',
            'input': 'day',
            'expected_braille': '"d',
            'expected_contractions': [
                (0, 3, 0, 2, 'day', '"d', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Initial-letter: ever',
            'input': 'ever',
            'expected_braille': '"e',
            'expected_contractions': [
                (0, 4, 0, 2, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Initial-letter: father',
            'input': 'father',
            'expected_braille': '"f',
            'expected_contractions': [
                (0, 6, 0, 2, 'father', '"f', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Initial-letter: name',
            'input': 'name',
            'expected_braille': '"n',
            'expected_contractions': [
                (0, 4, 0, 2, 'name', '"n', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Initial-letter: time',
            'input': 'time',
            'expected_braille': '"t',
            'expected_contractions': [
                (0, 4, 0, 2, 'time', '"t', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # FINAL-LETTER GROUPSIGNS (Section 10.8)
        # =====================================================================
        {
            'name': 'Final-letter: nation (-tion)',
            'input': 'nation',
            'expected_braille': 'na;n',
            'expected_contractions': [
                (2, 6, 2, 4, 'tion', ';n', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Final-letter: kindness (-ness)',
            'input': 'kindness',
            'expected_braille': 'k9d;s',
            'expected_contractions': [
                (1, 3, 1, 2, 'in', '9', 'LOWER_GROUPSIGN'),
                (4, 8, 3, 5, 'ness', ';s', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Final-letter: statement (-ment)',
            'input': 'statement',
            'expected_braille': '/ate;t',
            'expected_contractions': [
                (0, 2, 0, 1, 'st', '/', 'STRONG_GROUPSIGN'),
                (5, 9, 4, 6, 'ment', ';t', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Final-letter: beautiful (-ful)',
            'input': 'beautiful',
            'expected_braille': 'b1uti;l',
            'expected_contractions': [
                (1, 3, 1, 2, 'ea', '1', 'LOWER_GROUPSIGN'),
                (6, 9, 5, 7, 'ful', ';l', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
    ]

    passed = 0
    failed = 0
    errors = 0

    for test in test_cases:
        name = test['name']
        input_text = test['input']
        expected_braille = test['expected_braille']
        expected_contractions = test['expected_contractions']

        try:
            result = detect_contractions_detailed(input_text)

            # Check braille output
            braille_match = result.braille_text == expected_braille

            # Check contractions count
            count_match = len(result.contractions) == len(expected_contractions)

            # Check each contraction's exact values
            contractions_match = True
            mismatch_details = []

            if count_match:
                for i, (expected, actual) in enumerate(zip(expected_contractions, result.contractions)):
                    exp_ps, exp_pe, exp_bs, exp_be, exp_pt, exp_bt, exp_type = expected

                    if actual.print_start != exp_ps:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_start: expected {exp_ps}, got {actual.print_start}")
                    if actual.print_end != exp_pe:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_end: expected {exp_pe}, got {actual.print_end}")
                    if actual.braille_start != exp_bs:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_start: expected {exp_bs}, got {actual.braille_start}")
                    if actual.braille_end != exp_be:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_end: expected {exp_be}, got {actual.braille_end}")
                    if actual.print_text != exp_pt:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_text: expected {repr(exp_pt)}, got {repr(actual.print_text)}")
                    if actual.braille_text != exp_bt:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_text: expected {repr(exp_bt)}, got {repr(actual.braille_text)}")
                    if actual.contraction_type.name != exp_type:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] type: expected {exp_type}, got {actual.contraction_type.name}")
            else:
                contractions_match = False
                mismatch_details.append(f"  count: expected {len(expected_contractions)}, got {len(result.contractions)}")

            if braille_match and count_match and contractions_match:
                print(f"[PASS] {name}")
                passed += 1
            else:
                print(f"[FAIL] {name}")
                if not braille_match:
                    print(f"       Braille: expected {repr(expected_braille)}, got {repr(result.braille_text)}")
                for detail in mismatch_details:
                    print(f"      {detail}")
                if not count_match:
                    print(f"       Expected contractions:")
                    for e in expected_contractions:
                        print(f"         {e}")
                    print(f"       Got contractions:")
                    for c in result.contractions:
                        print(f"         ({c.print_start}, {c.print_end}, {c.braille_start}, {c.braille_end}, {repr(c.print_text)}, {repr(c.braille_text)}, {c.contraction_type.name})")
                failed += 1

        except Exception as e:
            print(f"[ERROR] {name}")
            print(f"        {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {errors} errors")
    print("=" * 70)

    return passed, failed, errors


def demo():
    """Run a demonstration of the contraction detector."""
    print("\n" + "=" * 70)
    print("CONTRACTION DETECTOR DEMO")
    print("=" * 70)

    test_sentences = [
        "The child will go with every friend.",
        "I can do it for you.",
        "This and that are knowledge.",
        "The quick brown fox jumps.",
    ]

    for sentence in test_sentences:
        print(f"\nInput: \"{sentence}\"")
        result = detect_contractions_detailed(sentence)
        print(f"Braille: {result.braille_unicode}")
        print(f"Contractions found: {len(result.contractions)}")

        for c in result.contractions:
            print(f"  - '{c.print_text}' [{c.print_start}:{c.print_end}] -> "
                  f"'{c.braille_unicode}' [{c.braille_start}:{c.braille_end}] "
                  f"({c.contraction_type.name})")


def run_edge_case_tests():
    """Run additional edge case tests to stress-test the algorithm with exact expected values."""

    print("\n" + "=" * 70)
    print("EDGE CASE TEST SUITE (EXACT VALUES)")
    print("=" * 70)

    edge_cases = [
        # =====================================================================
        # HYPHENATED WORDS
        # =====================================================================
        {
            'name': 'Hyphenated: self-confidence',
            'input': 'self-confidence',
            'expected_braille': 'self-3fid;e',
            'expected_contractions': [
                (5, 8, 5, 6, 'con', '3', 'LOWER_GROUPSIGN'),
                (11, 15, 9, 11, 'ence', ';e', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Hyphenated: mother-in-law',
            'input': 'mother-in-law',
            'expected_braille': '"m-9-law',
            'expected_contractions': [
                (0, 6, 0, 2, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
                (7, 9, 3, 4, 'in', '9', 'LOWER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Hyphenated: well-known',
            'input': 'well-known',
            'expected_braille': 'well-"kn',
            'expected_contractions': [
                (5, 9, 5, 7, 'know', '"k', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Hyphenated: twenty-one',
            'input': 'twenty-one',
            'expected_braille': 'tw5ty-"o',
            'expected_contractions': [
                (2, 4, 2, 3, 'en', '5', 'LOWER_GROUPSIGN'),
                (7, 10, 6, 8, 'one', '"o', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # DOUBLE CONTRACTIONS / COMPLEX APOSTROPHES
        # =====================================================================
        {
            'name': "Double contraction: couldn't",
            'input': "couldn't",
            'expected_braille': "cdn't",
            'expected_contractions': [
                # 'c' matches G1's 'c', rest is contracted: "ouldn't" -> "dn't"
                (1, 8, 1, 5, "ouldn't", "dn't", 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': "Double contraction: wouldn't",
            'input': "wouldn't",
            'expected_braille': "wdn't",
            'expected_contractions': [
                # 'w' matches G1's 'w', rest is contracted: "ouldn't" -> "dn't"
                (1, 8, 1, 5, "ouldn't", "dn't", 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': "Double contraction: shouldn't",
            'input': "shouldn't",
            'expected_braille': "%dn't",
            'expected_contractions': [
                # '%' (sh) doesn't match G1's 's', whole word is contracted
                (0, 9, 0, 5, "shouldn't", "%dn't", 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': "Triple contraction: couldn't've (informal)",
            'input': "couldn't've",
            'expected_braille': "cdn't've",
            'expected_contractions': [
                # 'c' matches G1's 'c', rest is contracted
                (1, 11, 1, 8, "ouldn't've", "dn't've", 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': "Possessive with contraction: child's",
            'input': "child's",
            'expected_braille': "*'s",
            'expected_contractions': [
                (0, 5, 0, 1, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': "Possessive: children's",
            'input': "children's",
            'expected_braille': "*n's",
            'expected_contractions': [
                (0, 8, 0, 2, 'children', '*n', 'SHORTFORM'),
            ],
        },
        {
            'name': "Possessive: mother's",
            'input': "mother's",
            'expected_braille': '"m\'s',
            'expected_contractions': [
                (0, 6, 0, 2, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # MULTIPLE SPACES AND WHITESPACE
        # =====================================================================
        {
            'name': 'Double space: the  child',
            'input': 'the  child',
            'expected_braille': '!  *',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (5, 10, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Triple space: the   and',
            'input': 'the   and',
            'expected_braille': '!   &',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (6, 9, 4, 5, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Tab character',
            'input': 'the\tchild',
            'expected_braille': '!\t*',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 9, 2, 3, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Newline character',
            'input': 'the\nchild',
            'expected_braille': '! *',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 9, 2, 3, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Mixed whitespace',
            'input': 'the \t\n child',
            'expected_braille': '! \t  *',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (7, 12, 5, 6, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Leading spaces',
            'input': '   the',
            'expected_braille': '   !',
            'expected_contractions': [
                (3, 6, 3, 4, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Trailing spaces',
            'input': 'the   ',
            'expected_braille': '!   ',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # ORDINAL NUMBERS AND MIXED ALPHANUMERIC
        # =====================================================================
        {
            'name': 'Ordinal: 1st',
            'input': '1st',
            'expected_braille': '#ast',
            'expected_contractions': [],
        },
        {
            'name': 'Ordinal: 2nd',
            'input': '2nd',
            'expected_braille': '#bnd',
            'expected_contractions': [],
        },
        {
            'name': 'Ordinal: 3rd',
            'input': '3rd',
            'expected_braille': '#crd',
            'expected_contractions': [],
        },
        {
            'name': 'Ordinal: 4th',
            'input': '4th',
            'expected_braille': '#dth',
            'expected_contractions': [],
        },
        {
            'name': 'Mixed: room 101',
            'input': 'room 101',
            'expected_braille': 'room #aja',
            'expected_contractions': [],
        },
        {
            'name': 'Mixed: a1b2c3',
            'input': 'a1b2c3',
            'expected_braille': 'a#a;b#b;c#c',
            'expected_contractions': [],
        },

        # =====================================================================
        # CURRENCY AND PERCENTAGES
        # =====================================================================
        {
            'name': 'Currency: $100',
            'input': '$100',
            'expected_braille': '`s#ajj',
            'expected_contractions': [],
        },
        {
            'name': 'Currency with text: costs $50',
            'input': 'costs $50',
            'expected_braille': 'co/s `s#ej',
            'expected_contractions': [
                (2, 4, 2, 3, 'st', '/', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Percentage: 50%',
            'input': '50%',
            'expected_braille': '#ej.0',
            'expected_contractions': [],
        },
        {
            'name': 'Percentage with text: about 50%',
            'input': 'about 50%',
            'expected_braille': 'ab #ej.0',
            'expected_contractions': [
                (0, 5, 0, 2, 'about', 'ab', 'SHORTFORM'),
            ],
        },

        # =====================================================================
        # ABBREVIATIONS AND TITLES
        # =====================================================================
        {
            'name': 'Abbreviation: Dr.',
            'input': 'Dr.',
            'expected_braille': ',dr4',
            'expected_contractions': [],
        },
        {
            'name': 'Abbreviation: Mr.',
            'input': 'Mr.',
            'expected_braille': ',mr4',
            'expected_contractions': [],
        },
        {
            'name': 'Abbreviation: Mrs.',
            'input': 'Mrs.',
            'expected_braille': ',mrs4',
            'expected_contractions': [],
        },
        {
            'name': 'Title with name: Dr. Smith',
            'input': 'Dr. Smith',
            'expected_braille': ',dr4 ,smi?',
            'expected_contractions': [
                (7, 9, 9, 10, 'th', '?', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Abbreviation: etc.',
            'input': 'etc.',
            'expected_braille': 'etc4',
            'expected_contractions': [],
        },
        {
            'name': 'Abbreviation: e.g.',
            'input': 'e.g.',
            'expected_braille': 'e4g4',
            'expected_contractions': [],
        },
        {
            'name': 'Abbreviation: i.e.',
            'input': 'i.e.',
            'expected_braille': 'i4e4',
            'expected_contractions': [],
        },

        # =====================================================================
        # ACRONYMS
        # =====================================================================
        {
            'name': 'Acronym: NASA',
            'input': 'NASA',
            'expected_braille': ',,nasa',
            'expected_contractions': [],
        },
        {
            'name': 'Acronym: FBI',
            'input': 'FBI',
            'expected_braille': ',,fbi',
            'expected_contractions': [],
        },
        {
            'name': 'Acronym: USA',
            'input': 'USA',
            'expected_braille': ',,usa',
            'expected_contractions': [],
        },
        {
            'name': 'Acronym in sentence: The FBI and CIA',
            'input': 'The FBI and CIA',
            'expected_braille': ',! ,,fbi & ,,cia',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (8, 11, 9, 10, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # SPECIAL PUNCTUATION
        # =====================================================================
        {
            'name': 'Ellipsis: the...',
            'input': 'the...',
            'expected_braille': '!444',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Ellipsis in sentence: and... then',
            'input': 'and... then',
            'expected_braille': '&444 !n',
            'expected_contractions': [
                (0, 3, 0, 1, 'and', '&', 'STRONG_CONTRACTION'),
                (7, 10, 5, 6, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Em-dash: the-child',
            'input': 'the\u2014child',
            'expected_braille': '!,-*',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'En-dash: pages 10-20',
            'input': 'pages 10\u201320',
            'expected_braille': 'pages #aj,-#bj',
            'expected_contractions': [],
        },
        {
            'name': 'Semicolon: the; and',
            'input': 'the; and',
            'expected_braille': '!2 &',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (5, 8, 3, 4, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Colon: the: child',
            'input': 'the: child',
            'expected_braille': '!3 *',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (5, 10, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },

        # =====================================================================
        # QUOTES AND BRACKETS
        # =====================================================================
        {
            'name': "Single quotes: 'the'",
            'input': "'the'",
            'expected_braille': "'!'",
            'expected_contractions': [
                (1, 4, 1, 2, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Double quotes: "the"',
            'input': '"the"',
            'expected_braille': '8!0',
            'expected_contractions': [
                (1, 4, 1, 2, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Smart quotes: "the"',
            'input': '\u201cthe\u201d',
            'expected_braille': '8!0',
            'expected_contractions': [
                (1, 4, 1, 2, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Parentheses: (the child)',
            'input': '(the child)',
            'expected_braille': '"<! *">',
            'expected_contractions': [
                (1, 4, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
                (5, 10, 4, 5, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Square brackets: [the]',
            'input': '[the]',
            'expected_braille': '.<!.>',
            'expected_contractions': [
                (1, 4, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Curly braces: {the}',
            'input': '{the}',
            'expected_braille': '_<!_>',
            'expected_contractions': [
                (1, 4, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Nested quotes: "she said \'the\'"',
            'input': "\"she said 'the'\"",
            'expected_braille': "8%e sd '!'0",
            'expected_contractions': [
                (1, 3, 1, 2, 'sh', '%', 'STRONG_GROUPSIGN'),
                (5, 9, 4, 6, 'said', 'sd', 'SHORTFORM'),
                (11, 14, 8, 9, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # CONTRACTIONS AT BOUNDARIES
        # =====================================================================
        {
            'name': 'Start of sentence: The quick',
            'input': 'The quick',
            'expected_braille': ',! qk',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 5, 'quick', 'qk', 'SHORTFORM'),
            ],
        },
        {
            'name': 'End of sentence: go with the.',
            'input': 'go with the.',
            'expected_braille': 'g ) !4',
            'expected_contractions': [
                (0, 2, 0, 1, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (3, 7, 2, 3, 'with', ')', 'STRONG_CONTRACTION'),
                (8, 11, 4, 5, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'After comma: hello, the',
            'input': 'hello, the',
            'expected_braille': 'hello1 !',
            'expected_contractions': [
                (7, 10, 7, 8, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Before comma: the, hello',
            'input': 'the, hello',
            'expected_braille': '!1 hello',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'After question: what? the',
            'input': 'what? the',
            'expected_braille': ':at8 !',
            'expected_contractions': [
                (0, 2, 0, 1, 'wh', ':', 'STRONG_GROUPSIGN'),
                (6, 9, 5, 6, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'After exclamation: wow! the',
            'input': 'wow! the',
            'expected_braille': 'w{6 !',
            'expected_contractions': [
                (1, 3, 1, 2, 'ow', '{', 'STRONG_GROUPSIGN'),
                (5, 8, 4, 5, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # VERY LONG WORDS
        # =====================================================================
        {
            'name': 'Long word: antidisestablishmentarianism',
            'input': 'antidisestablishmentarianism',
            'expected_braille': 'antidise/abli%;t>ianism',
            'expected_contractions': [
                (8, 10, 8, 9, 'st', '/', 'STRONG_GROUPSIGN'),
                (14, 16, 13, 14, 'sh', '%', 'STRONG_GROUPSIGN'),
                (16, 20, 14, 16, 'ment', ';t', 'FINAL_LETTER_GROUPSIGN'),
                (20, 22, 16, 17, 'ar', '>', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Long word: supercalifragilisticexpialidocious',
            'input': 'supercalifragilisticexpialidocious',
            'expected_braille': 'sup}califragili/icexpialidoci|s',
            'expected_contractions': [
                (3, 5, 3, 4, 'er', '}', 'STRONG_GROUPSIGN'),
                (16, 18, 15, 16, 'st', '/', 'STRONG_GROUPSIGN'),
                (31, 33, 29, 30, 'ou', '|', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Long word: pneumonoultramicroscopicsilicovolcanoconiosis',
            'input': 'pneumonoultramicroscopicsilicovolcanoconiosis',
            'expected_braille': 'pneumon|ltramicroscopicsilicovolcanoconiosis',
            'expected_contractions': [
                (7, 9, 7, 8, 'ou', '|', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # REPEATED LETTERS AND PATTERNS
        # =====================================================================
        {
            'name': 'Repeated letters: shhh',
            'input': 'shhh',
            'expected_braille': '%hh',
            'expected_contractions': [
                (0, 2, 0, 1, 'sh', '%', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Repeated letters: oooo',
            'input': 'oooo',
            'expected_braille': 'oooo',
            'expected_contractions': [],
        },
        {
            'name': 'Repeated word: the the the',
            'input': 'the the the',
            'expected_braille': '! ! !',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 7, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
                (8, 11, 4, 5, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Repeated contraction: and and and',
            'input': 'and and and',
            'expected_braille': '& & &',
            'expected_contractions': [
                (0, 3, 0, 1, 'and', '&', 'STRONG_CONTRACTION'),
                (4, 7, 2, 3, 'and', '&', 'STRONG_CONTRACTION'),
                (8, 11, 4, 5, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # CASE VARIATIONS
        # =====================================================================
        {
            'name': 'All caps sentence: THE CHILD',
            'input': 'THE CHILD',
            'expected_braille': ',,! ,,*',
            'expected_contractions': [
                (0, 3, 2, 3, 'THE', '!', 'STRONG_CONTRACTION'),
                (4, 9, 6, 7, 'CHILD', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'All lowercase: the child',
            'input': 'the child',
            'expected_braille': '! *',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 9, 2, 3, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Title case: The Child',
            'input': 'The Child',
            'expected_braille': ',! ,*',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 4, 5, 'Child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Mixed case: tHe ChIlD',
            'input': 'tHe ChIlD',
            'expected_braille': 't,he ,*,il,d',
            'expected_contractions': [
                (4, 6, 6, 7, 'Ch', '*', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Alternating caps: ThE cHiLd',
            'input': 'ThE cHiLd',
            'expected_braille': ',?,e c,hi,ld',
            'expected_contractions': [
                (0, 2, 1, 2, 'Th', '?', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # EDGE CASE WORDS
        # =====================================================================
        {
            'name': 'Word: a',
            'input': 'a',
            'expected_braille': 'a',
            'expected_contractions': [],
        },
        {
            'name': 'Word: I',
            'input': 'I',
            'expected_braille': ',i',
            'expected_contractions': [],
        },
        {
            'name': 'Word: be',
            'input': 'be',
            'expected_braille': '2',
            'expected_contractions': [
                (0, 2, 0, 1, 'be', '2', 'LOWER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Word: in',
            'input': 'in',
            'expected_braille': '9',
            'expected_contractions': [
                (0, 2, 0, 1, 'in', '9', 'LOWER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Word: to',
            'input': 'to',
            'expected_braille': 'to',
            'expected_contractions': [],
        },
        {
            'name': 'Word: go',
            'input': 'go',
            'expected_braille': 'g',
            'expected_contractions': [
                (0, 2, 0, 1, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # SUFFIX AND PREFIX PATTERNS
        # =====================================================================
        {
            'name': 'Prefix un-: undo',
            'input': 'undo',
            'expected_braille': 'undo',
            'expected_contractions': [],
        },
        {
            'name': 'Prefix re-: redo',
            'input': 'redo',
            'expected_braille': 'r$o',
            'expected_contractions': [
                (1, 3, 1, 2, 'ed', '$', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ing: going',
            'input': 'going',
            'expected_braille': 'go+',
            'expected_contractions': [
                (2, 5, 2, 3, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ed: walked',
            'input': 'walked',
            'expected_braille': 'walk$',
            'expected_contractions': [
                (4, 6, 4, 5, 'ed', '$', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -er: teacher',
            'input': 'teacher',
            'expected_braille': 't1*}',
            'expected_contractions': [
                (1, 3, 1, 2, 'ea', '1', 'LOWER_GROUPSIGN'),
                (3, 5, 2, 3, 'ch', '*', 'STRONG_GROUPSIGN'),
                (5, 7, 3, 4, 'er', '}', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -tion: nation',
            'input': 'nation',
            'expected_braille': 'na;n',
            'expected_contractions': [
                (2, 6, 2, 4, 'tion', ';n', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ness: kindness',
            'input': 'kindness',
            'expected_braille': 'k9d;s',
            'expected_contractions': [
                (1, 3, 1, 2, 'in', '9', 'LOWER_GROUPSIGN'),
                (4, 8, 3, 5, 'ness', ';s', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ment: government',
            'input': 'government',
            'expected_braille': 'gov}n;t',
            'expected_contractions': [
                (3, 5, 3, 4, 'er', '}', 'STRONG_GROUPSIGN'),
                (6, 10, 5, 7, 'ment', ';t', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # SPECIAL CHARACTERS AND UNICODE
        # =====================================================================
        {
            'name': 'Accented: cafe with accent',
            'input': 'caf\u00e9',
            'expected_braille': 'caf~/e',
            'expected_contractions': [],
        },
        {
            'name': 'Accented: naive with umlaut',
            'input': 'na\u00efve',
            'expected_braille': 'na~3ive',
            'expected_contractions': [],
        },
        {
            'name': 'Copyright symbol',
            'input': '\u00a9 the company',
            'expected_braille': '~c ! company',
            'expected_contractions': [
                (2, 5, 3, 4, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Registered trademark',
            'input': 'Brand\u00ae and more',
            'expected_braille': ',br&~r & m',
            'expected_contractions': [
                (2, 5, 3, 4, 'and', '&', 'STRONG_CONTRACTION'),
                (7, 10, 7, 8, 'and', '&', 'STRONG_CONTRACTION'),
                (11, 15, 9, 10, 'more', 'm', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Degree symbol',
            'input': '90\u00b0 angle',
            'expected_braille': '#ij~j angle',
            'expected_contractions': [],
        },

        # =====================================================================
        # CONTRACTIONS WITHIN LONGER SENTENCES
        # =====================================================================
        {
            'name': 'Long sentence with many contractions',
            'input': 'The child could not go with every friend because it would be just too much for the mother.',
            'expected_braille': ',! * cd n g ) e fr 2c x wd 2 j too m* = ! "m4',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
                (10, 15, 5, 7, 'could', 'cd', 'SHORTFORM'),
                (16, 19, 8, 9, 'not', 'n', 'ALPHABETIC_WORDSIGN'),
                (20, 22, 10, 11, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (23, 27, 12, 13, 'with', ')', 'STRONG_CONTRACTION'),
                (28, 33, 14, 15, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (34, 40, 16, 18, 'friend', 'fr', 'SHORTFORM'),
                (41, 48, 19, 21, 'because', '2c', 'SHORTFORM'),
                (49, 51, 22, 23, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
                (52, 57, 24, 26, 'would', 'wd', 'SHORTFORM'),
                (58, 60, 27, 28, 'be', '2', 'LOWER_GROUPSIGN'),
                (61, 65, 29, 30, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (71, 74, 36, 37, 'uch', '*', 'STRONG_GROUPSIGN'),
                (75, 78, 38, 39, 'for', '=', 'STRONG_CONTRACTION'),
                (79, 82, 40, 41, 'the', '!', 'STRONG_CONTRACTION'),
                (83, 89, 42, 44, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Sentence with no contractions',
            'input': 'A big cat sat on a mat.',
            'expected_braille': ',a big cat sat on a mat4',
            'expected_contractions': [],
        },
        {
            'name': 'Question with contractions',
            'input': 'Can you do it for the child?',
            'expected_braille': ',c y d x = ! *8',
            'expected_contractions': [
                (0, 3, 1, 2, 'Can', 'c', 'ALPHABETIC_WORDSIGN'),
                (4, 7, 3, 4, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (8, 10, 5, 6, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (11, 13, 7, 8, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
                (14, 17, 9, 10, 'for', '=', 'STRONG_CONTRACTION'),
                (18, 21, 11, 12, 'the', '!', 'STRONG_CONTRACTION'),
                (22, 27, 13, 14, 'child', '*', 'STRONG_WORDSIGN'),
            ],
        },
        {
            'name': 'Exclamation with contractions',
            'input': 'The child shall go with you!',
            'expected_braille': ',! * % g ) y6',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
                (10, 15, 5, 6, 'shall', '%', 'STRONG_WORDSIGN'),
                (16, 18, 7, 8, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (19, 23, 9, 10, 'with', ')', 'STRONG_CONTRACTION'),
                (24, 27, 11, 12, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # PUNCTUATION-HEAVY STRINGS
        # =====================================================================
        {
            'name': 'Only punctuation: ...',
            'input': '...',
            'expected_braille': '444',
            'expected_contractions': [],
        },
        {
            'name': 'Only punctuation: !!!',
            'input': '!!!',
            'expected_braille': '666',
            'expected_contractions': [],
        },
        {
            'name': 'Only punctuation: ???',
            'input': '???',
            'expected_braille': ';8;8;8',
            'expected_contractions': [],
        },
        {
            'name': 'Mixed punctuation: !?!?',
            'input': '!?!?',
            'expected_braille': '6;86;8',
            'expected_contractions': [],
        },

        # =====================================================================
        # EMPTY AND NEAR-EMPTY
        # =====================================================================
        {
            'name': 'Only whitespace: multiple spaces',
            'input': '     ',
            'expected_braille': '     ',
            'expected_contractions': [],
        },
        {
            'name': 'Only whitespace: tabs',
            'input': '\t\t\t',
            'expected_braille': '\t\t\t',
            'expected_contractions': [],
        },
        {
            'name': 'Only whitespace: newlines',
            'input': '\n\n\n',
            'expected_braille': '   ',
            'expected_contractions': [],
        },
        {
            'name': 'Only whitespace: mixed',
            'input': ' \t\n \t\n ',
            'expected_braille': ' \t  \t  ',
            'expected_contractions': [],
        },

        # =====================================================================
        # ADJACENT CONTRACTIONS (no space)
        # =====================================================================
        {
            'name': 'Adjacent: "theand" (not valid)',
            'input': 'theand',
            'expected_braille': '!&',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (3, 6, 1, 2, 'and', '&', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # ROMAN NUMERALS
        # =====================================================================
        {
            'name': 'Roman numeral: IV',
            'input': 'IV',
            'expected_braille': ',,iv',
            'expected_contractions': [],
        },
        {
            'name': 'Roman numeral: XII',
            'input': 'XII',
            'expected_braille': ',,xii',
            'expected_contractions': [],
        },
        {
            'name': 'Roman numeral with text: Chapter IV',
            'input': 'Chapter IV',
            'expected_braille': ',*apt} ,,iv',
            'expected_contractions': [
                (0, 2, 1, 2, 'Ch', '*', 'STRONG_GROUPSIGN'),
                (5, 7, 5, 6, 'er', '}', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # COMMON CONTRACTIONS IN SENTENCES
        # =====================================================================
        {
            'name': "I'm going",
            'input': "I'm going",
            'expected_braille': ",i'm go+",
            'expected_contractions': [
                (6, 9, 7, 8, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': "We've been there",
            'input': "We've been there",
            'expected_braille': ',we\'ve be5 "!',
            'expected_contractions': [
                (8, 10, 9, 10, 'en', '5', 'LOWER_GROUPSIGN'),
                (11, 16, 11, 13, 'there', '"!', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': "They'll do it",
            'input': "They'll do it",
            'expected_braille': ",!y'll d x",
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (8, 10, 7, 8, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (11, 13, 9, 10, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': "She'd have gone",
            'input': "She'd have gone",
            'expected_braille': ',%e\'d h g"o',
            'expected_contractions': [
                (0, 2, 1, 2, 'Sh', '%', 'STRONG_GROUPSIGN'),
                (6, 10, 6, 7, 'have', 'h', 'ALPHABETIC_WORDSIGN'),
                (12, 15, 9, 11, 'one', '"o', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # STRESS TESTS - VERY LONG TEXT
        # =====================================================================
        {
            'name': 'Very long text with many contractions',
            'input': 'The child could go with every friend and do just about everything for you. ' * 5,
            'expected_braille': ',! * cd g ) e fr & d j ab "ey?+ = y4 ,! * cd g ) e fr & d j ab "ey?+ = y4 ,! * cd g ) e fr & d j ab "ey?+ = y4 ,! * cd g ) e fr & d j ab "ey?+ = y4 ,! * cd g ) e fr & d j ab "ey?+ = y4 ',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
                (10, 15, 5, 7, 'could', 'cd', 'SHORTFORM'),
                (16, 18, 8, 9, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (19, 23, 10, 11, 'with', ')', 'STRONG_CONTRACTION'),
                (24, 29, 12, 13, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (30, 36, 14, 16, 'friend', 'fr', 'SHORTFORM'),
                (37, 40, 17, 18, 'and', '&', 'STRONG_CONTRACTION'),
                (41, 43, 19, 20, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (44, 48, 21, 22, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (49, 54, 23, 25, 'about', 'ab', 'SHORTFORM'),
                (55, 59, 26, 28, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (60, 62, 29, 30, 'th', '?', 'STRONG_GROUPSIGN'),
                (62, 65, 30, 31, 'ing', '+', 'STRONG_GROUPSIGN'),
                (66, 69, 32, 33, 'for', '=', 'STRONG_CONTRACTION'),
                (70, 73, 34, 35, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (75, 78, 38, 39, 'The', '!', 'STRONG_CONTRACTION'),
                (79, 84, 40, 41, 'child', '*', 'STRONG_WORDSIGN'),
                (85, 90, 42, 44, 'could', 'cd', 'SHORTFORM'),
                (91, 93, 45, 46, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (94, 98, 47, 48, 'with', ')', 'STRONG_CONTRACTION'),
                (99, 104, 49, 50, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (105, 111, 51, 53, 'friend', 'fr', 'SHORTFORM'),
                (112, 115, 54, 55, 'and', '&', 'STRONG_CONTRACTION'),
                (116, 118, 56, 57, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (119, 123, 58, 59, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (124, 129, 60, 62, 'about', 'ab', 'SHORTFORM'),
                (130, 134, 63, 65, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (135, 137, 66, 67, 'th', '?', 'STRONG_GROUPSIGN'),
                (137, 140, 67, 68, 'ing', '+', 'STRONG_GROUPSIGN'),
                (141, 144, 69, 70, 'for', '=', 'STRONG_CONTRACTION'),
                (145, 148, 71, 72, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (150, 153, 75, 76, 'The', '!', 'STRONG_CONTRACTION'),
                (154, 159, 77, 78, 'child', '*', 'STRONG_WORDSIGN'),
                (160, 165, 79, 81, 'could', 'cd', 'SHORTFORM'),
                (166, 168, 82, 83, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (169, 173, 84, 85, 'with', ')', 'STRONG_CONTRACTION'),
                (174, 179, 86, 87, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (180, 186, 88, 90, 'friend', 'fr', 'SHORTFORM'),
                (187, 190, 91, 92, 'and', '&', 'STRONG_CONTRACTION'),
                (191, 193, 93, 94, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (194, 198, 95, 96, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (199, 204, 97, 99, 'about', 'ab', 'SHORTFORM'),
                (205, 209, 100, 102, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (210, 212, 103, 104, 'th', '?', 'STRONG_GROUPSIGN'),
                (212, 215, 104, 105, 'ing', '+', 'STRONG_GROUPSIGN'),
                (216, 219, 106, 107, 'for', '=', 'STRONG_CONTRACTION'),
                (220, 223, 108, 109, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (225, 228, 112, 113, 'The', '!', 'STRONG_CONTRACTION'),
                (229, 234, 114, 115, 'child', '*', 'STRONG_WORDSIGN'),
                (235, 240, 116, 118, 'could', 'cd', 'SHORTFORM'),
                (241, 243, 119, 120, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (244, 248, 121, 122, 'with', ')', 'STRONG_CONTRACTION'),
                (249, 254, 123, 124, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (255, 261, 125, 127, 'friend', 'fr', 'SHORTFORM'),
                (262, 265, 128, 129, 'and', '&', 'STRONG_CONTRACTION'),
                (266, 268, 130, 131, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (269, 273, 132, 133, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (274, 279, 134, 136, 'about', 'ab', 'SHORTFORM'),
                (280, 284, 137, 139, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (285, 287, 140, 141, 'th', '?', 'STRONG_GROUPSIGN'),
                (287, 290, 141, 142, 'ing', '+', 'STRONG_GROUPSIGN'),
                (291, 294, 143, 144, 'for', '=', 'STRONG_CONTRACTION'),
                (295, 298, 145, 146, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (300, 303, 149, 150, 'The', '!', 'STRONG_CONTRACTION'),
                (304, 309, 151, 152, 'child', '*', 'STRONG_WORDSIGN'),
                (310, 315, 153, 155, 'could', 'cd', 'SHORTFORM'),
                (316, 318, 156, 157, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (319, 323, 158, 159, 'with', ')', 'STRONG_CONTRACTION'),
                (324, 329, 160, 161, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (330, 336, 162, 164, 'friend', 'fr', 'SHORTFORM'),
                (337, 340, 165, 166, 'and', '&', 'STRONG_CONTRACTION'),
                (341, 343, 167, 168, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (344, 348, 169, 170, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (349, 354, 171, 173, 'about', 'ab', 'SHORTFORM'),
                (355, 359, 174, 176, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (360, 362, 177, 178, 'th', '?', 'STRONG_GROUPSIGN'),
                (362, 365, 178, 179, 'ing', '+', 'STRONG_GROUPSIGN'),
                (366, 369, 180, 181, 'for', '=', 'STRONG_CONTRACTION'),
                (370, 373, 182, 183, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Paragraph with varied content',
            'input': '''The quick brown fox jumps over the lazy dog.
            This sentence has every letter of the alphabet.
            Can you believe it? I just learned about this today!
            The child will go with the mother and father.''',
            'expected_braille': ',! qk br{n fox jumps ov} ! lazy dog4             ,? s5t;e has e lr ( ! alphabet4             ,c y 2lieve x8 ,i j le>n$ ab ? td6             ,! * w g ) ! "m & "f4',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 5, 'quick', 'qk', 'SHORTFORM'),
                (12, 14, 8, 9, 'ow', '{', 'STRONG_GROUPSIGN'),
                (28, 30, 23, 24, 'er', '}', 'STRONG_GROUPSIGN'),
                (31, 34, 25, 26, 'the', '!', 'STRONG_CONTRACTION'),
                (57, 61, 50, 51, 'This', '?', 'STRONG_WORDSIGN'),
                (63, 65, 53, 54, 'en', '5', 'LOWER_GROUPSIGN'),
                (66, 70, 55, 57, 'ence', ';e', 'FINAL_LETTER_GROUPSIGN'),
                (75, 80, 62, 63, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (81, 87, 64, 66, 'letter', 'lr', 'SHORTFORM'),
                (88, 90, 67, 68, 'of', '(', 'STRONG_CONTRACTION'),
                (91, 94, 69, 70, 'the', '!', 'STRONG_CONTRACTION'),
                (117, 120, 94, 95, 'Can', 'c', 'ALPHABETIC_WORDSIGN'),
                (121, 124, 96, 97, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (125, 127, 98, 99, 'be', '2', 'LOWER_GROUPSIGN'),
                (133, 135, 105, 106, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
                (139, 143, 111, 112, 'just', 'j', 'ALPHABETIC_WORDSIGN'),
                (146, 148, 115, 116, 'ar', '>', 'STRONG_GROUPSIGN'),
                (149, 151, 117, 118, 'ed', '$', 'STRONG_GROUPSIGN'),
                (152, 157, 119, 121, 'about', 'ab', 'SHORTFORM'),
                (158, 162, 122, 123, 'this', '?', 'STRONG_WORDSIGN'),
                (163, 168, 124, 126, 'today', 'td', 'SHORTFORM'),
                (182, 185, 141, 142, 'The', '!', 'STRONG_CONTRACTION'),
                (186, 191, 143, 144, 'child', '*', 'STRONG_WORDSIGN'),
                (192, 196, 145, 146, 'will', 'w', 'ALPHABETIC_WORDSIGN'),
                (197, 199, 147, 148, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (200, 204, 149, 150, 'with', ')', 'STRONG_CONTRACTION'),
                (205, 208, 151, 152, 'the', '!', 'STRONG_CONTRACTION'),
                (209, 215, 153, 155, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
                (216, 219, 156, 157, 'and', '&', 'STRONG_CONTRACTION'),
                (220, 226, 158, 160, 'father', '"f', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # WORDS THAT LOOK LIKE CONTRACTIONS BUT AREN'T
        # =====================================================================
        {
            'name': 'Word: anthem (has th but might not contract)',
            'input': 'anthem',
            'expected_braille': 'an!m',
            'expected_contractions': [
                (2, 5, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: bother (has th and er)',
            'input': 'bother',
            'expected_braille': 'bo!r',
            'expected_contractions': [
                (2, 5, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: other (has th and er)',
            'input': 'other',
            'expected_braille': 'o!r',
            'expected_contractions': [
                (1, 4, 1, 2, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: father (initial-letter contraction)',
            'input': 'father',
            'expected_braille': '"f',
            'expected_contractions': [
                (0, 6, 0, 2, 'father', '"f', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # WORDS WITH MULTIPLE POTENTIAL CONTRACTIONS
        # =====================================================================
        {
            'name': 'Word: motherhood (mother + hood)',
            'input': 'motherhood',
            'expected_braille': '"mhood',
            'expected_contractions': [
                (0, 6, 0, 2, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: brotherhood (brother + hood)',
            'input': 'brotherhood',
            'expected_braille': 'bro!rhood',
            'expected_contractions': [
                (3, 6, 3, 4, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Word: neighborhood',
            'input': 'neighborhood',
            'expected_braille': 'nei<borhood',
            'expected_contractions': [
                (3, 5, 3, 4, 'gh', '<', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Word: childhood',
            'input': 'childhood',
            'expected_braille': '*ildhood',
            'expected_contractions': [
                (0, 2, 0, 1, 'ch', '*', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # COMPOUND WORDS
        # =====================================================================
        {
            'name': 'Compound: something',
            'input': 'something',
            'expected_braille': '"s?+',
            'expected_contractions': [
                (0, 4, 0, 2, 'some', '"s', 'INITIAL_LETTER_CONTRACTION'),
                (4, 6, 2, 3, 'th', '?', 'STRONG_GROUPSIGN'),
                (6, 9, 3, 4, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Compound: everything',
            'input': 'everything',
            'expected_braille': '"ey?+',
            'expected_contractions': [
                (0, 4, 0, 2, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (5, 7, 3, 4, 'th', '?', 'STRONG_GROUPSIGN'),
                (7, 10, 4, 5, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Compound: nothing',
            'input': 'nothing',
            'expected_braille': 'no?+',
            'expected_contractions': [
                (2, 4, 2, 3, 'th', '?', 'STRONG_GROUPSIGN'),
                (4, 7, 3, 4, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Compound: anything',
            'input': 'anything',
            'expected_braille': 'any?+',
            'expected_contractions': [
                (3, 5, 3, 4, 'th', '?', 'STRONG_GROUPSIGN'),
                (5, 8, 4, 5, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Compound: someone',
            'input': 'someone',
            'expected_braille': '"s"o',
            'expected_contractions': [
                (0, 4, 0, 2, 'some', '"s', 'INITIAL_LETTER_CONTRACTION'),
                (4, 7, 2, 4, 'one', '"o', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Compound: everyone',
            'input': 'everyone',
            'expected_braille': '"ey"o',
            'expected_contractions': [
                (0, 4, 0, 2, 'ever', '"e', 'INITIAL_LETTER_CONTRACTION'),
                (5, 8, 3, 5, 'one', '"o', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },

        # =====================================================================
        # WORDS ENDING IN COMMON SUFFIXES
        # =====================================================================
        {
            'name': 'Suffix -ful: wonderful',
            'input': 'wonderful',
            'expected_braille': 'wond};l',
            'expected_contractions': [
                (4, 6, 4, 5, 'er', '}', 'STRONG_GROUPSIGN'),
                (6, 9, 5, 7, 'ful', ';l', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -less: homeless',
            'input': 'homeless',
            'expected_braille': 'home.s',
            'expected_contractions': [
                (4, 8, 4, 6, 'less', '.s', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ness: happiness',
            'input': 'happiness',
            'expected_braille': 'happi;s',
            'expected_contractions': [
                # 'i' matches G1, so only "ness" -> ";s" is the contraction
                (5, 9, 5, 7, 'ness', ';s', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -ment: development',
            'input': 'development',
            'expected_braille': 'develop;t',
            'expected_contractions': [
                (7, 11, 7, 9, 'ment', ';t', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -tion: education',
            'input': 'education',
            'expected_braille': '$uca;n',
            'expected_contractions': [
                (0, 2, 0, 1, 'ed', '$', 'STRONG_GROUPSIGN'),
                (5, 9, 4, 6, 'tion', ';n', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },
        {
            'name': 'Suffix -sion: decision',
            'input': 'decision',
            'expected_braille': 'deci.n',
            'expected_contractions': [
                (4, 8, 4, 6, 'sion', '.n', 'FINAL_LETTER_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # SENTENCE BOUNDARY EDGE CASES
        # =====================================================================
        {
            'name': 'Multiple sentences with contractions',
            'input': 'The child is here. And the mother is there. For every friend, there is a place.',
            'expected_braille': ',! * is "h4 ,& ! "m is "!4 ,= e fr1 "! is a place4',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
                (4, 9, 3, 4, 'child', '*', 'STRONG_WORDSIGN'),
                (13, 17, 8, 10, 'here', '"h', 'INITIAL_LETTER_CONTRACTION'),
                (19, 22, 13, 14, 'And', '&', 'STRONG_CONTRACTION'),
                (23, 26, 15, 16, 'the', '!', 'STRONG_CONTRACTION'),
                (27, 33, 17, 19, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
                (37, 42, 23, 25, 'there', '"!', 'INITIAL_LETTER_CONTRACTION'),
                (44, 47, 28, 29, 'For', '=', 'STRONG_CONTRACTION'),
                (48, 53, 30, 31, 'every', 'e', 'ALPHABETIC_WORDSIGN'),
                (54, 60, 32, 34, 'friend', 'fr', 'SHORTFORM'),
                (62, 67, 36, 38, 'there', '"!', 'INITIAL_LETTER_CONTRACTION'),
            ],
        },
        {
            'name': 'Question and answer',
            'input': 'Can you do it? Yes, I can do it for you.',
            'expected_braille': ',c y d x8 ,yes1 ,i c d x = y4',
            'expected_contractions': [
                (0, 3, 1, 2, 'Can', 'c', 'ALPHABETIC_WORDSIGN'),
                (4, 7, 3, 4, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
                (8, 10, 5, 6, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (11, 13, 7, 8, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
                (22, 25, 19, 20, 'can', 'c', 'ALPHABETIC_WORDSIGN'),
                (26, 28, 21, 22, 'do', 'd', 'ALPHABETIC_WORDSIGN'),
                (29, 31, 23, 24, 'it', 'x', 'ALPHABETIC_WORDSIGN'),
                (32, 35, 25, 26, 'for', '=', 'STRONG_CONTRACTION'),
                (36, 39, 27, 28, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },
        {
            'name': 'Dialogue format',
            'input': '"The child," said the mother, "will go with you."',
            'expected_braille': '8,! *10 sd ! "m1 8w g ) y40',
            'expected_contractions': [
                (1, 4, 2, 3, 'The', '!', 'STRONG_CONTRACTION'),
                (5, 10, 4, 5, 'child', '*', 'STRONG_WORDSIGN'),
                (13, 17, 8, 10, 'said', 'sd', 'SHORTFORM'),
                (18, 21, 11, 12, 'the', '!', 'STRONG_CONTRACTION'),
                (22, 28, 13, 15, 'mother', '"m', 'INITIAL_LETTER_CONTRACTION'),
                (31, 35, 18, 19, 'will', 'w', 'ALPHABETIC_WORDSIGN'),
                (36, 38, 20, 21, 'go', 'g', 'ALPHABETIC_WORDSIGN'),
                (39, 43, 22, 23, 'with', ')', 'STRONG_CONTRACTION'),
                (44, 47, 24, 25, 'you', 'y', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # WORDS WITH APOSTROPHES IN VARIOUS POSITIONS
        # =====================================================================
        {
            'name': "Apostrophe at start: 'twas",
            'input': "'twas",
            'expected_braille': "'twas",
            'expected_contractions': [],
        },
        {
            'name': "Apostrophe: o'clock",
            'input': "o'clock",
            'expected_braille': "o'clock",
            'expected_contractions': [],
        },
        {
            'name': "Apostrophe: rock'n'roll",
            'input': "rock'n'roll",
            'expected_braille': "rock'n'roll",
            'expected_contractions': [],
        },

        # =====================================================================
        # NUMBERS AND ORDINALS IN CONTEXT
        # =====================================================================
        {
            'name': 'Date format: January 1st, 2024',
            'input': 'January 1st, 2024',
            'expected_braille': ',janu>y #ast1 #bjbd',
            'expected_contractions': [
                (4, 6, 5, 6, 'ar', '>', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Time format: 3:00 PM',
            'input': '3:00 PM',
            'expected_braille': '#c3#jj ,,pm',
            'expected_contractions': [],
        },
        {
            'name': 'Math: 2 + 2 = 4',
            'input': '2 + 2 = 4',
            'expected_braille': '#b "6 #b "7 #d',
            'expected_contractions': [],
        },

        # =====================================================================
        # SPECIAL WORD FORMS
        # =====================================================================
        {
            'name': 'Plural: children',
            'input': 'children',
            'expected_braille': '*n',
            'expected_contractions': [
                (0, 8, 0, 2, 'children', '*n', 'SHORTFORM'),
            ],
        },
        {
            'name': 'Past tense: walked',
            'input': 'walked',
            'expected_braille': 'walk$',
            'expected_contractions': [
                (4, 6, 4, 5, 'ed', '$', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Progressive: walking',
            'input': 'walking',
            'expected_braille': 'walk+',
            'expected_contractions': [
                (4, 7, 4, 5, 'ing', '+', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Comparative: better',
            'input': 'better',
            'expected_braille': 'bett}',
            'expected_contractions': [
                (4, 6, 4, 5, 'er', '}', 'STRONG_GROUPSIGN'),
            ],
        },
        {
            'name': 'Superlative: best',
            'input': 'best',
            'expected_braille': 'be/',
            'expected_contractions': [
                # 'be' matches G1, so only "st" -> "/" is the contraction
                (2, 4, 2, 3, 'st', '/', 'STRONG_GROUPSIGN'),
            ],
        },

        # =====================================================================
        # CONTRACTIONS IN DIFFERENT POSITIONS
        # =====================================================================
        {
            'name': 'Start: The cat',
            'input': 'The cat',
            'expected_braille': ',! cat',
            'expected_contractions': [
                (0, 3, 1, 2, 'The', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Middle: a the b',
            'input': 'a the b',
            'expected_braille': 'a ! ;b',
            'expected_contractions': [
                (2, 5, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'End: see the',
            'input': 'see the',
            'expected_braille': 'see !',
            'expected_contractions': [
                (4, 7, 4, 5, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Only: the',
            'input': 'the',
            'expected_braille': '!',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },

        # =====================================================================
        # UNICODE AND SPECIAL CHARACTERS
        # =====================================================================
        {
            'name': 'Bullet point: * the item',
            'input': '* the item',
            'expected_braille': '"9 ! item',
            'expected_contractions': [
                (2, 5, 3, 4, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'At sign: email@the.com',
            'input': 'email@the.com',
            'expected_braille': 'email`a!4com',
            'expected_contractions': [
                (6, 9, 7, 8, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Hash: #the',
            'input': '#the',
            'expected_braille': '_?!',
            'expected_contractions': [
                (1, 4, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Ampersand: this & that',
            'input': 'this & that',
            'expected_braille': '? `& t',
            'expected_contractions': [
                (0, 4, 0, 1, 'this', '?', 'STRONG_WORDSIGN'),
                (7, 11, 5, 6, 'that', 't', 'ALPHABETIC_WORDSIGN'),
            ],
        },

        # =====================================================================
        # EXTREME EDGE CASES
        # =====================================================================
        {
            'name': 'Single character repeated: aaaaaa',
            'input': 'aaaaaa',
            'expected_braille': 'aaaaaa',
            'expected_contractions': [],
        },
        {
            'name': 'All same contraction word: the the the the the',
            'input': 'the the the the the',
            'expected_braille': '! ! ! ! !',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (4, 7, 2, 3, 'the', '!', 'STRONG_CONTRACTION'),
                (8, 11, 4, 5, 'the', '!', 'STRONG_CONTRACTION'),
                (12, 15, 6, 7, 'the', '!', 'STRONG_CONTRACTION'),
                (16, 19, 8, 9, 'the', '!', 'STRONG_CONTRACTION'),
            ],
        },
        {
            'name': 'Very short words only: a I a I a I',
            'input': 'a I a I a I',
            'expected_braille': 'a ,i a ,i a ,i',
            'expected_contractions': [],
        },
        {
            'name': 'Mixed contractions and numbers: the 123 and 456 for',
            'input': 'the 123 and 456 for',
            'expected_braille': '! #abc & #def =',
            'expected_contractions': [
                (0, 3, 0, 1, 'the', '!', 'STRONG_CONTRACTION'),
                (8, 11, 7, 8, 'and', '&', 'STRONG_CONTRACTION'),
                (16, 19, 14, 15, 'for', '=', 'STRONG_CONTRACTION'),
            ],
        },
    ]

    passed = 0
    failed = 0
    errors = 0

    for test in edge_cases:
        name = test['name']
        input_text = test['input']
        expected_braille = test['expected_braille']
        expected_contractions = test['expected_contractions']

        try:
            result = detect_contractions_detailed(input_text)

            # Check braille output
            braille_match = result.braille_text == expected_braille

            # Check contraction count
            count_match = len(result.contractions) == len(expected_contractions)

            # Check each contraction exactly
            contractions_match = True
            mismatch_details = []

            if count_match:
                for i, (expected, actual) in enumerate(zip(expected_contractions, result.contractions)):
                    exp_ps, exp_pe, exp_bs, exp_be, exp_pt, exp_bt, exp_type = expected

                    if actual.print_start != exp_ps:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_start: expected {exp_ps}, got {actual.print_start}")
                    if actual.print_end != exp_pe:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_end: expected {exp_pe}, got {actual.print_end}")
                    if actual.braille_start != exp_bs:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_start: expected {exp_bs}, got {actual.braille_start}")
                    if actual.braille_end != exp_be:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_end: expected {exp_be}, got {actual.braille_end}")
                    if actual.print_text != exp_pt:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] print_text: expected {repr(exp_pt)}, got {repr(actual.print_text)}")
                    if actual.braille_text != exp_bt:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] braille_text: expected {repr(exp_bt)}, got {repr(actual.braille_text)}")
                    if actual.contraction_type.name != exp_type:
                        contractions_match = False
                        mismatch_details.append(f"  [{i}] type: expected {exp_type}, got {actual.contraction_type.name}")
            else:
                contractions_match = False
                mismatch_details.append(f"  count: expected {len(expected_contractions)}, got {len(result.contractions)}")

            if braille_match and count_match and contractions_match:
                print(f"[PASS] {name}")
                passed += 1
            else:
                print(f"[FAIL] {name}")
                if not braille_match:
                    print(f"       Braille: expected {repr(expected_braille)}, got {repr(result.braille_text)}")
                for detail in mismatch_details:
                    print(f"      {detail}")
                if not count_match:
                    print(f"       Expected contractions:")
                    for e in expected_contractions:
                        print(f"         {e}")
                    print(f"       Got contractions:")
                    for c in result.contractions:
                        print(f"         ({c.print_start}, {c.print_end}, {c.braille_start}, {c.braille_end}, {repr(c.print_text)}, {repr(c.braille_text)}, {c.contraction_type.name})")
                failed += 1

        except Exception as e:
            print(f"[ERROR] {name}")
            print(f"        {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            errors += 1

    print()
    print("=" * 70)
    print(f"EDGE CASE RESULTS: {passed} passed, {failed} failed, {errors} errors")
    print("=" * 70)

    return passed, failed, errors


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='UEB Contraction Detector')
    parser.add_argument('--test', action='store_true', help='Run test suite')
    parser.add_argument('--edge', action='store_true', help='Run edge case tests')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--demo', action='store_true', help='Run demo')
    parser.add_argument('text', nargs='?', help='Text to analyze')

    args = parser.parse_args()

    if args.all:
        run_tests()
        run_edge_case_tests()
        demo()
    elif args.test:
        run_tests()
    elif args.edge:
        run_edge_case_tests()
    elif args.demo:
        demo()
    elif args.text:
        result = detect_contractions_detailed(args.text)
        print(f"Input: {result.original_text}")
        print(f"Braille: {result.braille_unicode}")
        print(f"\nContractions ({len(result.contractions)}):")
        for c in result.contractions:
            print(f"  '{c.print_text}' [{c.print_start}:{c.print_end}] -> "
                  f"'{c.braille_unicode}' [{c.braille_start}:{c.braille_end}] "
                  f"({c.contraction_type.name})")
    else:
        run_tests()
        demo()
