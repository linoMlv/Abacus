"""Document exports (T7): tenant-scoped PDF / Excel restitution of the books.

Generation is server-side (zero-trust, MCP-ready) and streamed as an attachment.
PDFs use fpdf2 with the embedded IBM Plex Sans (brand-consistent, full Unicode);
spreadsheets use openpyxl. Data gathering (``data.py``) is kept apart from
rendering (``documents.py`` / ``pdf.py`` / ``xlsx.py``).
"""
