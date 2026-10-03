# -*- coding: utf-8 -*-

"""Tests for flowchart tables in the job database (seamm.Table, store_results)."""

import math

import pandas
import pytest

import molsystem
import seamm


@pytest.fixture()
def system_db(tmp_path):
    """A fresh variables context with a job database."""
    saved = seamm.flowchart_variables
    seamm.flowchart_variables = seamm.Variables()
    db = molsystem.SystemDB(filename=str(tmp_path / "seamm.db"))
    seamm.flowchart_variables.set_variable("_system_db", db)
    yield db
    db.close()
    seamm.flowchart_variables = saved


_results_parameter = {
    "default": {},
    "kind": "dictionary",
    "default_units": "",
    "enumeration": tuple(),
    "format_string": "",
    "description": "results",
    "help_text": "",
}


@pytest.fixture()
def node(system_db):
    """A node that stores results in tables."""
    node = seamm.Node(flowchart=seamm.Flowchart())
    node.parameters = seamm.Parameters(defaults={"results": _results_parameter})
    node._metadata = {
        "results": {
            "energy": {
                "description": "E",
                "dimensionality": "scalar",
                "type": "float",
                "units": "kJ/mol",
            },
            "n": {"description": "n", "dimensionality": "scalar", "type": "integer"},
            "ok": {"description": "ok", "dimensionality": "scalar", "type": "boolean"},
            "name": {"description": "nm", "dimensionality": "scalar", "type": "string"},
            "v": {"description": "v", "dimensionality": [3], "type": "float"},
            "charges": {
                "description": "q",
                "dimensionality": "scalar",
                "type": "float",
            },
        }
    }
    node.parameters["results"].value = {
        "energy": {"table": "T", "column": "Energy"},
        "n": {"table": "T", "column": "N"},
        "ok": {"table": "T", "column": "OK"},
        "name": {"table": "T", "column": "Name"},
        "v": {"table": "T", "column": "V"},
        "charges": {"table": "T", "column": "q_{key}"},
    }
    return node


def test_first_write_creates_row_0(node):
    """The commonest pattern: a new table, and store_results writes row 0."""
    node.store_results(data={"energy": 1.5})
    node.store_results(data={"n": 3})
    table = node.get_table("T")
    assert isinstance(table, seamm.Table)
    assert table.n_rows == 1
    assert table.columns == ["Energy (kJ/mol)", "N"]
    df = table.to_dataframe()
    assert df["Energy (kJ/mol)"].tolist() == [1.5]
    assert df["N"].tolist() == [3]


def test_row_created_by_write_gets_defaults(node):
    """Paul's decision: the other columns of a new row get their defaults."""
    node.store_results(data={"energy": 1.5, "n": 3, "ok": True, "name": "a"})
    table = node.get_table("T")
    table.next_row()
    node.store_results(data={"energy": 2.5})
    df = table.to_dataframe()
    assert df["N"].tolist() == [3, 0]
    assert df["N"].dtype == "int64"
    assert df["OK"].tolist() == [True, False]
    assert df["OK"].dtype == bool
    assert df["Name"].tolist() == ["a", ""]


def test_non_scalar_is_json(node):
    node.store_results(data={"v": [1.0, 2.0, 3.0]})
    table = node.get_table("T")
    assert table.column_type("V") == "json"
    assert table.get_cell("V") == "[1.0,2.0,3.0]"


def test_keyed_columns(node):
    node.store_results(data={"charges": {"O": -0.8, "H": 0.4}})
    table = node.get_table("T")
    assert table.columns == ["q_O", "q_H"]
    assert table.get_row() == {"q_O": -0.8, "q_H": 0.4}


def test_create_tables_false(node):
    with pytest.raises(RuntimeError, match="does not exist"):
        node.store_results(data={"energy": 1.0}, create_tables=False)


def test_loop_over_rows_updates_rows(node, system_db):
    """A loop over the rows of a table, writing into each current row."""
    table = seamm.Table.create(
        system_db, "T", columns=[("SMILES", "string", None)], index_column=None
    )
    node.set_variable("T", table)
    table.append_rows([{"SMILES": "O"}, {"SMILES": "C"}])
    for i, (row, values) in enumerate(table.rows()):
        table.current_row = row
        node.store_results(data={"energy": float(i)})
    df = table.to_dataframe()
    assert df["SMILES"].tolist() == ["O", "C"]
    assert df["Energy (kJ/mol)"].tolist() == [0.0, 1.0]


def test_next_row_at_either_end_of_loop(system_db):
    """'Go to the next row' before or after the write gives one row per pass."""
    for before in (True, False):
        table = seamm.Table.create(system_db, "T", columns=[("x", "integer", None)])
        for i in range(3):
            if before:
                table.next_row()
            table.set_cell("x", i)
            if not before:
                table.next_row()
        assert table.to_dataframe()["x"].tolist() == [0, 1, 2]


def test_index_column_lookup(system_db):
    table = seamm.Table.create(
        system_db,
        "T",
        columns=[("name", "string", None), ("x", "float", None)],
        index_column="name",
    )
    table.append_rows([{"name": "a", "x": 1.0}, {"name": "b", "x": 2.0}])
    row = table.locate(key="b")
    assert table.get_cell("x", row) == 2.0
    assert table.label(row) == "b"
    table["current index"] = "a"
    assert table["current index"] == "a"
    assert table.get_cell("x") == 1.0
    with pytest.raises(KeyError):
        table.locate(key="zz")


def test_position_lookup(system_db):
    table = seamm.Table.create(system_db, "T", columns=[("x", "float", None)])
    table.append_rows([{"x": 1.0}, {"x": 2.0}])
    assert table.label(table.locate(position=1)) == 1
    with pytest.raises(KeyError):
        table.locate(position=2)
    table["current index"] = 0
    assert table.get_cell("x") == 1.0
    table["current index"] = 2
    assert table.current_row is None
    assert table["current index"] == 2


def test_rows_where(system_db):
    table = seamm.Table.create(
        system_db, "T", columns=[("name", "string", None), ("x", "float", None)]
    )
    table.append_rows(
        [{"name": "water", "x": 1.0}, {"name": "ethanol", "x": 2.0}, {"x": 3.0}]
    )

    def names(where):
        return [values["name"] for _, values in table.rows(where=where)]

    assert names(("x", ">", "1.5")) == ["ethanol", ""]
    assert names(("X", "between", "1", "2")) == ["water", "ethanol"]
    assert names(("name", "contains", "an")) == ["ethanol"]
    assert names(("name", "contains regexp", "^w")) == ["water"]
    assert names(("name", "is empty", "")) == [""]
    assert names(("name", "is not empty", "")) == ["water", "ethanol"]
    with pytest.raises(ValueError):
        names(("nope", "==", "1"))


def test_convert(system_db):
    table = seamm.Table.create(
        system_db,
        "T",
        columns=[("b", "boolean", None), ("i", "integer", None), ("f", "float", None)],
    )
    assert table.convert("b", "False") is False
    assert table.convert("b", "yes") is True
    assert table.convert("i", "3") == 3
    assert table.convert("f", "2") == 2.0
    with pytest.raises(ValueError):
        table.convert("b", "maybe")


def test_export_and_read(system_db, tmp_path):
    table = seamm.Table.create(
        system_db,
        "T",
        columns=[("name", "string", None), ("x", "float", None), ("n", "integer", 0)],
    )
    table.append_rows([{"name": "a", "x": 1.5, "n": 1}, {"name": "b", "n": 2}])
    path = tmp_path / "t.csv"
    table.export(str(path))
    assert path.read_text() == "name,x,n\na,1.5,1\nb,,2\n"
    assert table.filename == str(path)
    assert table["filename"] == str(path)

    copy = seamm.Table.read(system_db, "U", str(path), index_column="name")
    assert copy.n_rows == 2
    assert copy.column_type("n") == "integer"
    assert copy.current_row == copy.locate(key="a")
    out = tmp_path / "u.csv"
    copy.export(str(out))
    assert out.read_text() == "name,x,n\na,1.5,1\nb,,2\n"

    for suffix in (".json", ".xlsx", ".txt"):
        table.export(str(tmp_path / f"t{suffix}"))
        assert (tmp_path / f"t{suffix}").exists()
    with pytest.raises(RuntimeError, match="Cannot write"):
        table.export(str(tmp_path / "t.doc"))


def test_legacy_keys(system_db):
    table = seamm.Table.create(system_db, "T", columns=[("x", "float", None)])
    assert table["type"] == "table"
    assert "filename" not in table
    assert table["loop index"] is False
    table["loop index"] = True
    assert table["loop index"] is True
    assert table["index column"] is None
    assert math.isnan(table["defaults"]["x"])
    df = table["table"]
    assert isinstance(df, pandas.DataFrame)

    # Assigning a DataFrame replaces the contents (for unconverted code).
    table["table"] = pandas.DataFrame({"x": [1.0, 2.0]})
    assert table.n_rows == 2
    assert table.label(table.current_row) == 1
    assert table["loop index"] is True


def test_get_table_adopts_existing(system_db):
    """A table in the database but not yet a variable is used as is."""
    seamm.Table.create(system_db, "T", columns=[("x", "float", None)]).append_row(x=1.0)
    node = seamm.Node(flowchart=seamm.Flowchart())
    table = node.get_table("T", create=False)
    assert table.n_rows == 1


def test_legacy_handle_refused(node):
    node.set_variable("T", {"type": "pandas", "table": pandas.DataFrame()})
    with pytest.raises(RuntimeError, match="predates tables"):
        node.store_results(data={"energy": 1.0})


def test_read_only_database(tmp_path):
    path = tmp_path / "seamm.db"
    db = molsystem.SystemDB(filename=str(path))
    db.db.commit()
    db.close()
    db = molsystem.SystemDB(filename=f"file:{path}?mode=ro")
    with pytest.raises(PermissionError, match="read-only"):
        seamm.Table.create(db, "T")
    db.close()


class _Plugin(seamm.Node):
    pass


def test_check_table_plugins(monkeypatch):
    """Old table plug-ins are refused before the flowchart runs."""
    flowchart = seamm.Flowchart()
    node = _Plugin(flowchart=flowchart)
    flowchart.add_node(node)
    monkeypatch.setattr(_Plugin, "__module__", "table_step.table")
    monkeypatch.setattr(
        _Plugin, "version", property(lambda self: "2026.9.30"), raising=False
    )
    problems = seamm.table.check_table_plugins(flowchart)
    assert len(problems) == 1
    assert "table_step 2026.9.30 is too old" in problems[0]

    monkeypatch.setattr(_Plugin, "version", property(lambda self: "2099.1.1"))
    assert seamm.table.check_table_plugins(flowchart) == []

    # A development checkout is assumed to be current.
    monkeypatch.setattr(
        _Plugin, "version", property(lambda self: "2026.9.30+3.g1234abc.dirty")
    )
    assert seamm.table.check_table_plugins(flowchart) == []


def test_read_only_navigation(tmp_path):
    """In a read-only database, tables can be navigated, looped over and saved."""
    path = tmp_path / "seamm.db"
    db = molsystem.SystemDB(filename=str(path))
    table = seamm.Table.create(db, "T", columns=[("x", "integer", None)])
    table.append_rows([{"x": 1}, {"x": 2}])
    db.db.commit()
    db.close()

    db = molsystem.SystemDB(filename=f"file:{path}?mode=ro")
    table = seamm.Table(db, "T")
    assert table.read_only
    table["loop index"] = True
    assert table["loop index"] is True
    seen = []
    for row, values in table.rows():
        table.current_row = row
        seen.append(table.get_cell("x"))
    assert seen == [1, 2]
    table.next_row()
    assert table.current_row is None
    out = tmp_path / "t.csv"
    table.export(str(out))
    assert out.read_text() == "x\n1\n2\n"
    assert table.filename == str(out)
    with pytest.raises(PermissionError, match="read-only"):
        table.set_cell("x", 3, row=table.locate(position=0))
    db.close()


def test_missing_values_in_selection(system_db):
    """Missing values fail the tests instead of raising, as NaN did."""
    table = seamm.Table.create(
        system_db, "T", columns=[("n", "integer", None), ("s", "string", None)]
    )
    table.append_rows([{"n": 1, "s": "ab"}, {"n": 2, "s": "cd"}])
    table.set_cell("n", None, row=table.locate(position=0))
    table.set_cell("s", None, row=table.locate(position=0))

    def count(where):
        return len(list(table.rows(where=where)))

    assert count(("n", ">", "0")) == 1
    assert count(("n", "between", "0", "5")) == 1
    assert count(("s", "contains", "c")) == 1
    assert count(("s", "does not contain", "c")) == 1
    assert count(("n", "!=", "2")) == 1
    assert count(("s", "is empty", "")) == 1


def test_replace_keeps_declared_types(system_db):
    table = seamm.Table.create(
        system_db,
        "T",
        columns=[("name", "string", None), ("j", "json", None)],
        index_column="name",
    )
    df = pandas.DataFrame({"name": ["a"], "j": ["[1]"], "x": [1.5]})
    table["table"] = df
    assert table.column_type("j") == "json"
    assert table.column_type("x") == "float"
    assert table.index_column == "name"


def test_json_round_trip(system_db, tmp_path):
    table = seamm.Table.create(
        system_db,
        "T",
        columns=[("name", "string", None), ("x", "float", None)],
        index_column="name",
    )
    table.append_rows([{"name": "a", "x": 1.5}, {"name": "b", "x": 2.5}])
    path = tmp_path / "t.json"
    table.export(str(path))
    copy = seamm.Table.read(system_db, "U", str(path), index_column="name")
    assert copy.to_dataframe().equals(table.to_dataframe())


def test_step_completed_commits(system_db):
    seamm.Table.create(system_db, "T", columns=[("x", "integer", None)]).append_row(x=1)
    assert system_db.db.in_transaction
    seamm.step_completed()
    assert not system_db.db.in_transaction
