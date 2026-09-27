# -*- coding: utf-8 -*-
"""A second installation searches its own data first, then ~/SEAMM's."""

import importlib.resources

import seamm
from seamm.dashboard_handler import DashboardHandler

TEMPLATE = (importlib.resources.files("seamm") / "data" / "dashboards.ini").read_text()


def test_data_path_for_second_installation(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SEAMM_ROOT", str(home / "SEAMM_DEV"))
    fc = seamm.Flowchart()
    fc.in_jobserver = False
    assert fc.data_path == [
        home / ".seamm.d" / "data",
        home / "SEAMM_DEV" / "data",
        home / "SEAMM" / "data",
    ]
    fc.root_directory = str(tmp_path / "Job_000001")
    fc.in_jobserver = True
    assert fc.data_path[0] == tmp_path / "Job_000001" / "data"


def test_data_path_for_default_installation(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SEAMM_ROOT", str(home / "SEAMM"))
    fc = seamm.Flowchart()
    fc.in_jobserver = False
    assert fc.data_path == [home / ".seamm.d" / "data", home / "SEAMM" / "data"]


def test_dashboards_ini_falls_back_to_default_installation(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SEAMM_ROOT", str(home / "SEAMM_DEV"))
    (home / "SEAMM").mkdir(parents=True)
    (home / "SEAMM" / "dashboards.ini").write_text(TEMPLATE)
    assert DashboardHandler().configfile == home / "SEAMM" / "dashboards.ini"

    (home / "SEAMM_DEV").mkdir()
    (home / "SEAMM_DEV" / "dashboards.ini").write_text(TEMPLATE)
    assert DashboardHandler().configfile == home / "SEAMM_DEV" / "dashboards.ini"
