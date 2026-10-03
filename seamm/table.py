# -*- coding: utf-8 -*-

"""Flowchart tables, stored in the job's database.

A table is a flowchart variable whose value is a :class:`Table`. The data live in
the job's ``seamm.db`` (see ``molsystem.user_tables``); this object is a handle
on them with the operations the steps need: columns, appending rows, the current
row, cells, iterating rows, and exporting to files.

Rows are identified internally; flowcharts see the index column's value, or the
0-based position of the row when there is no index column.

For code written for the earlier in-memory tables, the handle also answers the
old dictionary keys: ``"table"`` gives a fresh DataFrame copy (changes to it are
not saved), ``"current index"``, ``"index column"``, ``"defaults"``,
``"filename"`` and ``"loop index"``.
"""

import logging
import math
from pathlib import Path, PurePath
import re

import pandas

logger = logging.getLogger(__name__)

#: The file types tables can be read from and written to.
file_types = (".csv", ".json", ".xlsx", ".txt")

#: The comparisons available when selecting rows.
operators = (
    "==",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "between",
    "contains",
    "does not contain",
    "contains regexp",
    "does not contain regexp",
    "is empty",
    "is not empty",
)

_legacy_keys = (
    "type",
    "table",
    "current index",
    "index column",
    "defaults",
    "filename",
    "loop index",
)


class Table:
    """A flowchart table, stored in the database.

    Parameters
    ----------
    system_db : molsystem.SystemDB
        The job's database.
    name : str
        The table's name.
    """

    def __init__(self, system_db, name):
        self._system_db = system_db
        self._name = name
        # Navigation state (current row, loop flag, file) kept here when the
        # database is read-only, so that reading a table still works.
        self._local = {}
        if name not in system_db.user_tables:
            raise KeyError(f"There is no table '{name}'.")

    def __repr__(self):
        return f"Table('{self._name}', {self.n_rows} rows)"

    @classmethod
    def create(cls, system_db, name, columns=(), index_column=None, replace=True):
        """Create a table, replacing any existing one of that name.

        Parameters
        ----------
        columns : [(name, type, default)]
            ``type`` is boolean, integer, float, string or json; a default of None
            means the type's default.
        """
        system_db.user_tables.create(
            name, columns=columns, index_column=index_column, replace=replace
        )
        return cls(system_db, name)

    @classmethod
    def from_dataframe(cls, system_db, name, df, index_column=None, metadata=None):
        """Create a table from a DataFrame, replacing any existing one."""
        system_db.user_tables.from_dataframe(
            name, df, index_column=index_column, metadata=metadata, replace=True
        )
        return cls(system_db, name)

    @classmethod
    def read(cls, system_db, name, filename, file_type=None, index_column=None):
        """Create a table from a file, replacing any existing one.

        Parameters
        ----------
        file_type : str
            One of .csv, .json, .xlsx or .txt; by default the file's extension.
        """
        if file_type is None or file_type == "from extension":
            file_type = PurePath(filename).suffix
        if file_type == ".csv":
            df = pandas.read_csv(filename, index_col=False)
        elif file_type == ".json":
            # export() writes orient="table", which keeps the index and types.
            try:
                df = pandas.read_json(filename, orient="table")
            except Exception:
                df = pandas.read_json(filename)
        elif file_type == ".xlsx":
            df = pandas.read_excel(filename, index_col=False)
        elif file_type == ".txt":
            df = pandas.read_fwf(filename, index_col=False)
        else:
            raise RuntimeError(
                f"Cannot read tables from files of type '{file_type}' ('{filename}'). "
                f"Known types: {', '.join(file_types)}"
            )
        if df.index.name is not None:
            # e.g. a JSON file written with its index
            df = df.reset_index()
        if index_column is not None and index_column not in df.columns:
            columns = ", ".join(str(c) for c in df.columns)
            raise ValueError(
                f"The index column '{index_column}' is not in the table: columns = "
                f"{columns}"
            )
        return cls.from_dataframe(
            system_db,
            name,
            df,
            index_column=index_column,
            metadata={"filename": str(filename)},
        )

    # The data in the database
    @property
    def _table(self):
        return self._system_db.user_tables[self._name]

    @property
    def name(self):
        return self._name

    @property
    def columns(self):
        """The column names, in order."""
        return self._table.columns

    @property
    def defaults(self):
        """The default value of each column."""
        table = self._table
        return {column: table.default(column) for column in table.columns}

    @property
    def index_column(self):
        """The column whose values identify the rows, or None."""
        return self._table.index_column

    @property
    def n_rows(self):
        return self._table.n_rows

    @property
    def filename(self):
        """The file the table was read from or last saved to, or None."""
        return self._get_state("filename")

    @filename.setter
    def filename(self, value):
        self._set_state("filename", None if value is None else str(value))

    @property
    def read_only(self):
        """Whether the table is in a read-only database."""
        return self._system_db.user_tables.read_only

    def _get_state(self, key):
        """Navigation state: the current row, the loop flag or the file."""
        if key in self._local:
            return self._local[key]
        if key == "current_row":
            return self._table.current_row
        return self._table.metadata.get(key)

    def _set_state(self, key, value):
        if key == "current_row":
            table = self._table
            if value is not None and not table.has_row(value):
                raise KeyError(f"Table '{self._name}' has no row with id {value}.")
            if self.read_only:
                self._local[key] = value
            else:
                table.current_row = value
        elif self.read_only:
            self._local[key] = value
        else:
            self._table.set_metadata(key, value)

    def column_type(self, column):
        """The declared type of a column: boolean, integer, float, string or json."""
        return self._table.column_type(column)

    def add_column(self, name, coltype="string", default=None):
        """Add a column, filling any existing rows with its default.

        Does nothing if the column exists. Returns whether it was added.
        """
        return self._table.add_column(name, coltype, default)

    def append_row(self, **values):
        """Append a row and make it the current row. Missing columns get defaults."""
        return self._table.append_row(**values)

    def append_rows(self, rows):
        """Append rows (dicts) and make the last one the current row."""
        return self._table.append_rows(rows)

    # Rows
    @property
    def current_row(self):
        """The current row, or None if the next write appends a row."""
        return self._get_state("current_row")

    @current_row.setter
    def current_row(self, row):
        self._set_state("current_row", row)

    def locate(self, key=None, position=None):
        """The row with the given index-column value or 0-based position.

        Raises KeyError if there is no such row.
        """
        table = self._table
        if key is not None:
            index = table.index_column
            if index is None:
                raise KeyError(
                    f"Table '{self._name}' has no index column to look up '{key}'."
                )
            rows = table.find(index, key)
            if len(rows) == 0:
                raise KeyError(f"Table '{self._name}' has no row '{key}'.")
            return rows[0]
        if position is None:
            raise ValueError("locate needs a key or a position.")
        row = table.rowid_at(int(position))
        if row is None:
            raise KeyError(
                f"Table '{self._name}' has no row at position {position}: it has "
                f"{table.n_rows} rows."
            )
        return row

    def label(self, row):
        """How flowcharts see a row: its index-column value, or its position."""
        table = self._table
        index = table.index_column
        if index is None:
            return table.position(row)
        return table.get_cell(row, index)

    def next_row(self):
        """Move to the next row: past the last row, the next write appends one.

        Already past the last row, this does nothing, so "go to the next row" works
        at either end of a loop body that writes one row per iteration.
        """
        current = self.current_row
        if current is not None:
            self.current_row = self._table.next_rowid(current)

    def set_cell(self, column, value, row=None):
        """Set a value, by default in the current row.

        When the current row is past the last row, this appends the row, filling
        the other columns with their defaults, and makes it the current row.
        """
        table = self._table
        if row is None:
            row = self.current_row
            if row is None:
                table.append_row(**{column: value})
                return
        table.set_cell(row, column, value)

    def get_cell(self, column, row=None):
        """Get a value, by default from the current row."""
        table = self._table
        if row is None:
            row = self.current_row
            if row is None:
                raise IndexError(
                    f"Table '{self._name}' has no current row: it is past the last "
                    "row."
                )
        return table.get_cell(row, column)

    def get_row(self, row=None):
        """The values in a row, by default the current row, as a dict."""
        if row is None:
            row = self.current_row
            if row is None:
                raise IndexError(f"Table '{self._name}' has no current row.")
        return self._table.get_row(row)

    def rows(self, where=None):
        """Iterate over (row, values) in order.

        Parameters
        ----------
        where : (column, operator, value[, value2])
            Optional selection with one of ``operators``. ``value`` is converted
            to the column's type. ``between`` uses ``value2`` too.
        """
        table = self._table
        if where is None:
            yield from table.iter_rows()
            return
        column, op, value, *rest = where
        value2 = rest[0] if len(rest) > 0 else None
        column = self._find_column(column)
        if op in ("==", "!=", ">", ">=", "<", "<=", "between"):
            value = self.convert(column, value)
            if op == "between":
                value2 = self.convert(column, value2)
        for row, values in table.iter_rows():
            if _test(values[column], op, value, value2):
                yield row, values

    def _find_column(self, column):
        """The column with this name, matched without regard to case."""
        columns = self.columns
        if column in columns:
            return column
        for name in columns:
            if name.lower() == str(column).lower():
                return name
        raise ValueError(f"Table '{self._name}' has no column '{column}'.")

    def convert(self, column, value):
        """Convert a value (e.g. text from a dialog) to a column's type."""
        coltype = self._table.column_type(column)
        if coltype == "integer":
            return int(value)
        if coltype == "float":
            return float(value)
        if coltype == "boolean":
            if isinstance(value, str):
                text = value.strip().lower()
                if text in ("true", "yes", "1", "t", "y"):
                    return True
                if text in ("false", "no", "0", "f", "n", ""):
                    return False
                raise ValueError(f"'{value}' is not a boolean value.")
            return bool(value)
        return value if isinstance(value, str) else str(value)

    # Output
    def to_dataframe(self):
        """A copy of the table as a pandas DataFrame. Changes to it are not saved."""
        return self._table.to_dataframe()

    def to_string(self):
        """The table as text, as the Table step prints it."""
        df = self.to_dataframe()
        return df.to_string(header=True, index=self.index_column is not None)

    def export(self, filename, file_type=None):
        """Write the table to a file and remember the file.

        Parameters
        ----------
        file_type : str
            One of .csv, .json, .xlsx or .txt; by default the file's extension.
        """
        if file_type is None or file_type == "from extension":
            file_type = PurePath(filename).suffix
        with_index = self.index_column is not None
        df = self.to_dataframe()
        if file_type == ".csv":
            df.to_csv(filename, index=with_index, header=True)
        elif file_type == ".json":
            df.to_json(filename, indent=4, orient="table", index=with_index)
        elif file_type == ".xlsx":
            df.to_excel(filename, index=with_index)
        elif file_type == ".txt":
            Path(filename).write_text(df.to_string(header=True, index=with_index))
        else:
            raise RuntimeError(
                f"Cannot write tables to files of type '{file_type}' ('{filename}'). "
                f"Known types: {', '.join(file_types)}"
            )
        self.filename = filename

    # The keys of the earlier in-memory table handles
    def __contains__(self, key):
        if key == "filename":
            return self.filename is not None
        return key in _legacy_keys

    def __getitem__(self, key):
        if key == "type":
            return "table"
        if key == "table":
            logger.warning(
                f"Table '{self._name}': handle['table'] is a copy of the table; "
                "changes to it are not saved. Use the Table methods."
            )
            return self.to_dataframe()
        if key == "current index":
            row = self.current_row
            if row is None:
                return self.n_rows if self.index_column is None else None
            return self.label(row)
        if key == "index column":
            return self.index_column
        if key == "defaults":
            return self.defaults
        if key == "filename":
            filename = self.filename
            if filename is None:
                raise KeyError("filename")
            return filename
        if key == "loop index":
            return bool(self._get_state("loop index"))
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "current index":
            if self.index_column is not None:
                self.current_row = self.locate(key=value)
            elif value == self.n_rows:
                self.current_row = None
            else:
                self.current_row = self.locate(position=value)
        elif key == "filename":
            self.filename = value
        elif key == "loop index":
            self._set_state("loop index", bool(value) or None)
        elif key == "table" and isinstance(value, pandas.DataFrame):
            # Replace the contents, keeping the name, index column, file and the
            # declared types and defaults of the columns that remain.
            index = self.index_column
            df = value
            if df.index.name is not None:
                df = df.reset_index()
            if index is not None and index not in df.columns:
                index = None
            self._system_db.user_tables.from_dataframe(
                self._name,
                df,
                index_column=index,
                metadata=self._table.metadata,
                replace=True,
                definitions=self._table.column_definitions,
            )
            self.current_row = (
                self._table.rowid_at(self.n_rows - 1) if self.n_rows > 0 else None
            )
        else:
            raise KeyError(f"Cannot set '{key}' of table '{self._name}'.")


def _test(row_value, op, value, value2=None):
    """Whether a value passes one of the row-selection tests."""
    if op == "is empty":
        return row_value is None or row_value == "" or _isnan(row_value)
    if op == "is not empty":
        return not (row_value is None or row_value == "" or _isnan(row_value))
    if row_value is None or _isnan(row_value):
        # A missing value fails every test except the negative ones, as NaN did
        # for the comparisons.
        return op == "!=" or op.startswith("does not")
    if op == "==":
        return row_value == value
    if op == "!=":
        return row_value != value
    if op == ">":
        return row_value > value
    if op == ">=":
        return row_value >= value
    if op == "<":
        return row_value < value
    if op == "<=":
        return row_value <= value
    if op == "between":
        return value <= row_value <= value2
    if op == "contains":
        return value in row_value
    if op == "does not contain":
        return value not in row_value
    if op == "contains regexp":
        return re.search(value, row_value) is not None
    if op == "does not contain regexp":
        return re.search(value, row_value) is None
    if op == "is empty":
        return row_value is None or row_value == "" or _isnan(row_value)
    if op == "is not empty":
        return not (row_value is None or row_value == "" or _isnan(row_value))
    raise NotImplementedError(f"Row selection '{op}' is not implemented.")


def _isnan(value):
    return isinstance(value, float) and math.isnan(value)


def is_legacy_table(value):
    """Whether a variable holds a table from before tables were in the database."""
    return isinstance(value, dict) and value.get("type") == "pandas"


def legacy_table_error(name):
    """The error for a table made by a plug-in older than tables in the database."""
    return RuntimeError(
        f"Table '{name}' was made by a plug-in that predates tables in the job "
        "database (an in-memory pandas table). Update table_step, loop_step, "
        "properties_step and geometry_analysis_step to their latest versions."
    )


#: The plug-ins that handle tables directly, and the first version of each that
#: uses tables in the database. Older ones cannot run with this seamm.
table_plugins = {
    "table_step": "2026.10.3",
    "loop_step": "2026.10.3",
    "properties_step": "2026.10.3",
    "geometry_analysis_step": "2026.10.3",
}


def check_table_plugins(flowchart):
    """Check, before running, that the flowchart's table plug-ins are new enough.

    Returns a list of messages, empty if all is well.
    """
    from packaging.version import InvalidVersion, Version

    problems = {}
    for node in _all_nodes(flowchart):
        package = type(node).__module__.split(".")[0]
        if package not in table_plugins:
            continue
        minimum = table_plugins[package]
        try:
            version = Version(str(node.version))
        except InvalidVersion:
            continue
        # A development checkout (e.g. 2026.9.30+3.g1234abc) is assumed current.
        too_old = version.local is None and version < Version(minimum)
        if too_old:
            problems[package] = (
                f"{package} {node.version} is too old for this version of seamm, "
                f"which keeps tables in the job database: update it to {minimum} or "
                "later."
            )
    return [*problems.values()]


def _all_nodes(flowchart):
    """The nodes of a flowchart and of any subflowcharts."""
    for node in flowchart:
        yield node
        subflowchart = getattr(node, "subflowchart", None)
        if subflowchart is not None and subflowchart is not flowchart:
            yield from _all_nodes(subflowchart)
