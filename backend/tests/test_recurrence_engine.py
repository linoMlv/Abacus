"""Pure date arithmetic of the recurrence engine."""

from datetime import date

from models import Periodicite
from recurrence_engine import add_months, next_echeance


def test_add_months_clamps_to_end_of_month():
    # 31 January + 1 month has no 31st in February → clamped.
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap year
    assert add_months(date(2026, 1, 15), 12) == date(2027, 1, 15)


def test_next_echeance_per_periodicite():
    d = date(2026, 3, 10)
    assert next_echeance(d, Periodicite.HEBDOMADAIRE) == date(2026, 3, 17)
    assert next_echeance(d, Periodicite.MENSUELLE) == date(2026, 4, 10)
    assert next_echeance(d, Periodicite.TRIMESTRIELLE) == date(2026, 6, 10)
    assert next_echeance(d, Periodicite.ANNUELLE) == date(2027, 3, 10)
