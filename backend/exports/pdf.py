"""Branded PDF base: a house style shared by every exported document.

A consistent header (Abacus wordmark + association, title, period), footer
(page numbers + generation date) and a tabular helper, all in IBM Plex Sans
to match the app. Colors mirror the frontend design tokens.
"""

from datetime import date
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import TableCellFillMode
from fpdf.fonts import FontFace

from .format import fmt_date

_FONT_DIR = Path(__file__).parent / "fonts"

# Design tokens (RGB), aligned with the frontend.
INK = (15, 23, 42)
INK_SOFT = (51, 65, 85)
MUTED = (100, 116, 139)
HAIRLINE = (226, 232, 240)
ACCENT = (37, 99, 235)
RECETTE = (4, 120, 87)
DEPENSE = (220, 38, 38)
ZEBRA = (248, 250, 252)

_HEADINGS = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=INK)


class AbacusPDF(FPDF):
    """A4 portrait document with the Abacus header/footer and table helper."""

    def __init__(self, *, association_name: str, title: str, subtitle: str = ""):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.association_name = association_name
        self.doc_title = title
        self.doc_subtitle = subtitle
        self.set_margins(15, 14, 15)
        self.set_auto_page_break(auto=True, margin=16)
        self.add_font("plex", "", str(_FONT_DIR / "IBMPlexSans-Regular.ttf"))
        self.add_font("plex", "B", str(_FONT_DIR / "IBMPlexSans-SemiBold.ttf"))
        self.set_title(title)
        self.set_creator("Abacus")

    @property
    def _usable_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self) -> None:
        half = self._usable_width / 2
        self.set_y(12)
        self.set_font("plex", "B", 13)
        self.set_text_color(*ACCENT)
        self.cell(half, 7, "Abacus", align="L")
        self.set_font("plex", "", 10)
        self.set_text_color(*MUTED)
        self.cell(
            half, 7, self.association_name, align="R", new_x="LMARGIN", new_y="NEXT"
        )

        self.ln(1)
        self.set_font("plex", "B", 17)
        self.set_text_color(*INK)
        self.cell(0, 9, self.doc_title, new_x="LMARGIN", new_y="NEXT")
        if self.doc_subtitle:
            self.set_font("plex", "", 10)
            self.set_text_color(*MUTED)
            self.cell(0, 5, self.doc_subtitle, new_x="LMARGIN", new_y="NEXT")

        self.ln(2)
        self.set_draw_color(*HAIRLINE)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(5)
        self.set_text_color(*INK)

    def footer(self) -> None:
        half = self._usable_width / 2
        self.set_y(-13)
        self.set_font("plex", "", 8)
        self.set_text_color(*MUTED)
        self.cell(half, 5, f"Page {self.page_no()}/{{nb}}", align="L")
        self.cell(half, 5, f"Généré le {fmt_date(date.today())}", align="R")

    def section_title(self, text: str) -> None:
        self.set_font("plex", "B", 11)
        self.set_text_color(*INK)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def summary(
        self, pairs: list[tuple[str, str, tuple[int, int, int] | None]]
    ) -> None:
        """A compact label/value summary block (e.g. opening/closing balances)."""
        for label, value, color in pairs:
            self.set_font("plex", "", 9)
            self.set_text_color(*MUTED)
            self.cell(55, 6, label, align="L")
            self.set_font("plex", "B", 9)
            self.set_text_color(*(color or INK))
            self.cell(0, 6, value, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)
        self.set_text_color(*INK)

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        *,
        widths: tuple[float, ...],
        aligns: tuple[str, ...],
        total_row: list[str] | None = None,
    ) -> None:
        """Render a striped table with a dark heading row and an optional bold total."""
        self.set_font("plex", "", 9)
        self.set_text_color(*INK)
        self.set_draw_color(*HAIRLINE)
        with super().table(
            col_widths=widths,
            text_align=aligns,
            headings_style=_HEADINGS,
            cell_fill_color=ZEBRA,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            borders_layout="HORIZONTAL_LINES",
            line_height=6,
            width=self._usable_width,
        ) as table:
            head = table.row()
            for label in headers:
                head.cell(label)
            for row_cells in rows:
                row = table.row()
                for cell in row_cells:
                    row.cell(cell)
            if total_row is not None:
                bold = FontFace(emphasis="BOLD")
                row = table.row()
                for cell in total_row:
                    row.cell(cell, style=bold)

    def to_bytes(self) -> bytes:
        return bytes(self.output())
