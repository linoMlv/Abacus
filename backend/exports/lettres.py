"""French number- and amount-in-words (pure).

Used to spell out the amount on a fiscal receipt. Handles the French spelling
rules: ``et`` at 21/31/…/71, hyphens elsewhere, the ``quatre-vingts`` / ``cents``
plural (an ``s`` only when multiplied and not followed by another number), and
the invariable ``mille``.
"""

from decimal import Decimal

_UNITS = [
    "zéro",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "treize",
    "quatorze",
    "quinze",
    "seize",
    "dix-sept",
    "dix-huit",
    "dix-neuf",
]
_TENS = {
    2: "vingt",
    3: "trente",
    4: "quarante",
    5: "cinquante",
    6: "soixante",
    8: "quatre-vingt",
}


def _below_100(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    ten, unit = divmod(n, 10)
    if ten in (7, 9):  # 70-79 / 90-99 build on soixante / quatre-vingt + 10-19
        base = _TENS[ten - 1]
        rest = _below_100(10 + unit)
        # "soixante et onze" (71) keeps the "et"; quatre-vingt-onze (91) never does.
        liaison = " et " if unit == 1 and ten == 7 else "-"
        return f"{base}{liaison}{rest}"
    word = _TENS[ten]
    if unit == 0:
        # quatre-vingts takes an s only when it ends the number.
        return "quatre-vingts" if ten == 8 else word
    if unit == 1 and ten != 8:  # vingt et un … soixante et un (not quatre-vingt-un)
        return f"{word} et un"
    return f"{word}-{_UNITS[unit]}"


def _below_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        return _below_100(rest)
    if hundreds == 1:
        head = "cent"
    else:
        head = f"{_UNITS[hundreds]} cent"
    if rest == 0:
        # "cent"/"deux cents": plural s only when multiplied and nothing follows.
        return f"{_UNITS[hundreds]} cents" if hundreds > 1 else "cent"
    return f"{head} {_below_100(rest)}"


def nombre_en_lettres(n: int) -> str:
    """Spell a non-negative integer in French."""
    if n < 0:
        raise ValueError("Le nombre doit être positif.")
    if n < 1000:
        return _below_1000(n)

    parts: list[str] = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        head = "un million" if millions == 1 else f"{_below_1000(millions)} millions"
        parts.append(head)
    thousands, units = divmod(rest, 1000)
    if thousands:
        # "mille" is invariable and elided for exactly one thousand.
        parts.append("mille" if thousands == 1 else f"{_below_1000(thousands)} mille")
    if units:
        parts.append(_below_1000(units))
    return " ".join(parts)


def montant_en_lettres(montant: Decimal) -> str:
    """Spell a euro amount in French, e.g. ``"douze euros et cinquante centimes"``."""
    montant = montant.quantize(Decimal("0.01"))
    euros = int(montant)
    centimes = int((montant - euros) * 100)
    # "euro" stays singular for zéro and un (zéro euro, un euro).
    words = f"{nombre_en_lettres(euros)} {'euro' if euros <= 1 else 'euros'}"
    if centimes:
        unite = "centime" if centimes == 1 else "centimes"
        words += f" et {nombre_en_lettres(centimes)} {unite}"
    return words
