==========================
Tables in a plug-in
==========================

A flowchart's tables -- made by the Table step, or by a step storing its results
into a table -- are kept in the job's database, ``seamm.db``, beside the
structures (since seamm 2026.10.3; before that they were pandas DataFrames in
memory). A table is a flowchart variable whose value is a :class:`seamm.Table`,
a handle on the data in the database.

Writing results
---------------

Most plug-ins never touch a table directly: ``Node.store_results()`` writes the
results the user asked for into the tables they named, creating the table and
its columns as needed. The column's type and default come from the result's
metadata (``boolean``, ``integer``, ``float``, ``string``; non-scalar results are
``json``). The value goes into the table's *current row*; if the current row is
past the end of the table, the write appends a row, whose other columns get
their defaults.

Working with a table
--------------------

``self.get_table(name)`` returns the table, creating it if needed
(``create=False`` raises instead). Its methods:

``columns``, ``n_rows``, ``index_column``, ``column_type(column)``
    The column names in order, the number of rows, the column identifying rows (or
    ``None``), and a column's declared type.
``add_column(name, type, default)``
    Adds a column, filling existing rows with the default; does nothing if the
    column exists.
``append_row(**values)``, ``append_rows([dict, ...])``
    Append rows; missing columns get their defaults; the last row appended becomes
    the current row.
``current_row``, ``locate(key=...)``, ``locate(position=...)``, ``next_row()``
    The current row, a row by its index-column value or 0-based position, and moving
    to the next row (past the last row, the next write appends one).
``set_cell(column, value, row=None)``, ``get_cell(column, row=None)``, ``get_row(row=None)``
    Values in a row, by default the current one.
``rows(where=None)``
    Iterate over ``(row, values)``; ``where`` is ``(column, operator, value[,
    value2])`` with the Loop step's operators (``==``, ``>``, ``between``,
    ``contains``, ``is empty``, ...).
``to_dataframe()``, ``export(filename)``, ``Table.read(...)``
    A pandas copy for printing, plotting or analysis (changes to it are not
    saved), writing csv/json/xlsx/txt, and reading a file into a new table.

Rows are identified internally; flowcharts see a row as its index-column value,
or its position when the table has no index column.

Code written for the in-memory tables
-------------------------------------

The handle still answers the old dictionary keys. ``table["table"]`` returns a
*copy* of the table as a DataFrame and logs a warning: changes to it are not
saved. Assigning a DataFrame to ``table["table"]`` replaces the table's contents.
``"current index"``, ``"index column"``, ``"defaults"``, ``"filename"`` and
``"loop index"`` work as before. A plug-in that creates its own
``{"type": "pandas", ...}`` table cannot work with this seamm; the Table, Loop,
Properties and Geometry Analysis steps were converted, and seamm refuses, before
the flowchart runs, older versions of them.

Committing
----------

The job database is committed after each step (``seamm.step_completed()``,
called by the flowchart evaluator and the Loop step). A database opened
read-only can be read, but writing a table raises ``PermissionError``.
