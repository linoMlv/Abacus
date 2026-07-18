"""One-off migration of a MySQL dump into the PostgreSQL database.

The legacy Abacus ran on MySQL with the *same* logical schema as today
(identical table and column names, UUID string primary keys). A ``mysqldump`` /
phpMyAdmin ``.sql`` export is therefore only a *dialect* away from what
PostgreSQL needs — no id or column remapping, just format conversion:

* backtick identifiers -> double-quoted identifiers (which also quotes the
  reserved words ``group`` and ``user``);
* MySQL string escapes (``\\'``, ``\\\\``, ``\\n`` …) -> PostgreSQL literals
  (single quotes doubled, backslashes kept verbatim under
  ``standard_conforming_strings``);
* ``tinyint(1)`` 0/1 -> ``boolean`` FALSE/TRUE.

Only data is imported: the schema must already exist (run ``alembic upgrade
head`` first). Rows are loaded parents-first inside a single transaction, so a
failure commits nothing. The ``operationtype`` enum and timestamps are emitted
as unquoted-type SQL literals, which PostgreSQL casts implicitly.

The parser is a small quote-aware scanner rather than a regex: string values in
this data legitimately contain ``;``, ``),(``, commas and apostrophes, which a
naive split would mangle.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from database import engine

# Insertion order respects foreign keys (parents before children).
TABLE_ORDER = ["association", "balance", "operation", "api_key", "log_entry"]

# Tables that may appear in a dump but must not be imported: alembic_version is
# owned by alembic, refresh_session holds ephemeral auth sessions.
SKIP_TABLES = {"alembic_version", "refresh_session"}

# Columns stored as boolean in PostgreSQL but dumped as tinyint(1) by MySQL.
BOOLEAN_COLUMNS = {"api_key": {"is_active"}}

# How many rows to bundle per INSERT statement.
_BATCH_SIZE = 500

# MySQL backslash escape sequences -> the character they represent. Any other
# escaped character stands for itself (MySQL's documented behavior).
_MYSQL_ESCAPES = {
    "0": "\0",
    "b": "\b",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "Z": "\x1a",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


class MysqlImportError(RuntimeError):
    """Raised for malformed dumps or an unsafe target database."""


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def _iter_statements(text: str):
    """Yield complete SQL statements, splitting on ``;`` outside strings.

    Skips ``--``/``#`` line comments, ``/* */`` block comments and backtick
    identifiers so their contents never affect statement or string boundaries.
    """
    i, n = 0, len(text)
    buf: list[str] = []
    while i < n:
        c = text[i]
        # Line comments.
        if c in "-#":
            if c == "#" or text[i : i + 2] == "--":
                nl = text.find("\n", i)
                i = n if nl == -1 else nl
                continue
        # Block comments (including MySQL's /*! conditional comments).
        if text[i : i + 2] == "/*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        # Backtick-quoted identifier.
        if c == "`":
            end = text.find("`", i + 1)
            buf.append(text[i : (n if end == -1 else end + 1)])
            i = n if end == -1 else end + 1
            continue
        # Single-quoted string: consume it whole.
        if c == "'":
            j = _skip_string(text, i)
            buf.append(text[i:j])
            i = j
            continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                yield stmt
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        yield tail


def _skip_string(text: str, i: int) -> int:
    """Return the index just past a single-quoted string starting at ``i``."""
    n = len(text)
    i += 1  # opening quote
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2  # escaped character
            continue
        if c == "'":
            if i + 1 < n and text[i + 1] == "'":
                i += 2  # doubled quote -> literal quote, still inside
                continue
            return i + 1  # closing quote
        i += 1
    raise MysqlImportError("Unterminated string literal in dump.")


def _decode_string(raw: str) -> str:
    """Decode the body of a MySQL string literal (between the quotes)."""
    out: list[str] = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n:
            out.append(_MYSQL_ESCAPES.get(raw[i + 1], raw[i + 1]))
            i += 2
        elif c == "'" and i + 1 < n and raw[i + 1] == "'":
            out.append("'")
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


# A parsed cell: ("null", None) | ("str", <decoded>) | ("raw", <verbatim>).
Cell = tuple[str, object]


def _scan_row(body: str) -> list[Cell]:
    """Parse one ``(...)`` tuple body into a list of typed cells."""
    cells: list[Cell] = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c in " \t\r\n,":
            i += 1
            continue
        if c == "'":
            j = _skip_string(body, i)
            cells.append(("str", _decode_string(body[i + 1 : j - 1])))
            i = j
            continue
        j = i
        while j < n and body[j] != ",":
            j += 1
        token = body[i:j].strip()
        cells.append(("null", None) if token.upper() == "NULL" else ("raw", token))
        i = j
    return cells


def _iter_row_bodies(values_sql: str):
    """Yield the inner text of each top-level ``(...)`` group in a VALUES clause."""
    depth, start, i, n = 0, -1, 0, len(values_sql)
    while i < n:
        c = values_sql[i]
        if c == "'":
            i = _skip_string(values_sql, i)
            continue
        if c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                yield values_sql[start:i]
        i += 1


def _parse_insert(statement: str) -> tuple[str, list[str], list[list[Cell]]] | None:
    """Parse ``INSERT INTO `t` (`c`,...) VALUES (...),(...)`` into structured data.

    Returns ``(table, columns, rows)`` or ``None`` if the statement is not an
    INSERT we recognize.
    """
    head = statement.lstrip()
    if not head[:11].upper().startswith("INSERT INTO"):
        return None

    rest = head[11:].lstrip()
    if not rest.startswith("`"):
        return None
    tick = rest.find("`", 1)
    table = rest[1:tick]

    rest = rest[tick + 1 :].lstrip()
    if not rest.startswith("("):
        raise MysqlImportError(f"Missing column list for table {table!r}.")
    close = rest.find(")")
    columns = [col.strip().strip("`") for col in rest[1:close].split(",")]

    values_kw = rest.upper().find("VALUES", close)
    if values_kw == -1:
        raise MysqlImportError(f"Missing VALUES clause for table {table!r}.")
    values_sql = rest[values_kw + len("VALUES") :]

    rows: list[list[Cell]] = []
    for body in _iter_row_bodies(values_sql):
        row = _scan_row(body)
        if len(row) != len(columns):
            raise MysqlImportError(
                f"Table {table!r}: row has {len(row)} values but "
                f"{len(columns)} columns."
            )
        rows.append(row)
    return table, columns, rows


def parse_dump(text: str) -> dict[str, tuple[list[str], list[list[Cell]]]]:
    """Extract ``{table: (columns, rows)}`` for every importable table."""
    tables: dict[str, tuple[list[str], list[list[Cell]]]] = {}
    for statement in _iter_statements(text):
        parsed = _parse_insert(statement)
        if parsed is None:
            continue
        table, columns, rows = parsed
        if table in SKIP_TABLES:
            continue
        if table in tables:
            tables[table][1].extend(rows)
        else:
            tables[table] = (columns, rows)
    return tables


# --------------------------------------------------------------------------- #
# SQL generation
# --------------------------------------------------------------------------- #
def _cell_to_sql(table: str, column: str, cell: Cell) -> str:
    kind, data = cell
    if column in BOOLEAN_COLUMNS.get(table, ()):
        if kind == "null":
            return "NULL"
        if data in ("0", "1"):
            return "TRUE" if data == "1" else "FALSE"
        raise MysqlImportError(
            f"Unexpected boolean value {data!r} for {table}.{column}."
        )
    if kind == "null":
        return "NULL"
    if kind == "str":
        return "'" + str(data).replace("'", "''") + "'"
    return str(data)  # raw numeric / enum literal, verbatim


def _row_to_sql(table: str, columns: list[str], row: list[Cell]) -> str:
    cells = (_cell_to_sql(table, col, cell) for col, cell in zip(columns, row))
    return "(" + ",".join(cells) + ")"


def _insert_statements(table: str, columns: list[str], rows: list[list[Cell]]):
    """Yield batched multi-row INSERT statements for a table."""
    col_list = ",".join(f'"{c}"' for c in columns)
    prefix = f'INSERT INTO "{table}" ({col_list}) VALUES '
    for start in range(0, len(rows), _BATCH_SIZE):
        batch = rows[start : start + _BATCH_SIZE]
        yield prefix + ",".join(_row_to_sql(table, columns, r) for r in batch)


# --------------------------------------------------------------------------- #
# Migration
# --------------------------------------------------------------------------- #
def migrate_mysql_dump(path: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Import a MySQL dump into PostgreSQL; return ``{table: rows_imported}``.

    The schema must already exist and the target tables must be empty. Runs in a
    single transaction: with ``dry_run`` it rolls back after validating.
    """
    text = Path(path).read_text(encoding="utf-8")
    tables = parse_dump(text)

    unknown = set(tables) - set(TABLE_ORDER)
    if unknown:
        raise MysqlImportError(f"Unrecognized tables in dump: {sorted(unknown)}.")

    inspector = inspect(engine)
    present = [t for t in TABLE_ORDER if t in tables]
    missing = [t for t in present if not inspector.has_table(t)]
    if missing:
        raise MysqlImportError(
            f"Target schema is missing tables {missing}. "
            "Run 'alembic upgrade head' before importing."
        )

    conn = engine.connect()
    trans = conn.begin()
    try:
        non_empty = {
            t: count
            for t in TABLE_ORDER
            if inspector.has_table(t)
            and (count := conn.exec_driver_sql(f'SELECT count(*) FROM "{t}"').scalar())
        }
        if non_empty:
            raise MysqlImportError(
                "Target database is not empty: "
                + ", ".join(f"{k}={v}" for k, v in non_empty.items())
                + ". Refusing to import."
            )

        # Execute the generated INSERTs on the raw DBAPI cursor with no bound
        # parameters, so the driver performs no '%' placeholder interpolation:
        # log_entry paths and user agents legitimately contain '%'. The values
        # are our own data with identifiers and strings already quoted.
        cursor = conn.connection.cursor()
        imported: dict[str, int] = {}
        try:
            for table in TABLE_ORDER:
                if table not in tables:
                    continue
                columns, rows = tables[table]
                for statement in _insert_statements(table, columns, rows):
                    cursor.execute(statement)
                imported[table] = len(rows)
        finally:
            cursor.close()

        # Validate: what we parsed is what landed in the database.
        for table, expected in imported.items():
            actual = conn.exec_driver_sql(f'SELECT count(*) FROM "{table}"').scalar()
            if actual != expected:
                raise MysqlImportError(
                    f"Validation failed for {table}: parsed {expected}, "
                    f"database has {actual}."
                )

        if dry_run:
            trans.rollback()
        else:
            trans.commit()
    except Exception:
        if trans.is_active:
            trans.rollback()
        raise
    finally:
        conn.close()

    return imported
