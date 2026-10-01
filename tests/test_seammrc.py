#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""~/.seamm.d/seammrc holds the dashboards' credentials and tokens. Each test uses a
home directory of its own, never the real file."""

import configparser
import threading

import pytest

from seamm.seammrc import SEAMMrc

CONTENT = """\
[VERSION]
file = 1.0

[Dashboard: dev]
user = someone
password = secret
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".seamm.d").mkdir()
    return tmp_path


def sections(path):
    config = configparser.ConfigParser()
    config.read(path)
    return config.sections()


def test_concurrent_use_keeps_the_file(home):
    """Threads creating Flowcharts (each makes a SEAMMrc) at the same time wiped the
    file down to [VERSION] (the MCP server's warm-up, 2026-10-01)."""
    path = home / ".seamm.d" / "seammrc"
    path.write_text(CONTENT)

    def work():
        for _ in range(200):
            SEAMMrc()

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sections(path) == ["VERSION", "Dashboard: dev"]
    assert sorted(p.name for p in path.parent.iterdir()) == ["seammrc"]


def test_an_empty_existing_file_is_not_replaced(home):
    """Another program may be writing it."""
    path = home / ".seamm.d" / "seammrc"
    path.write_text("")
    SEAMMrc()
    assert path.read_text() == ""


def test_created_when_missing(home):
    path = home / ".seamm.d" / "seammrc"
    rc = SEAMMrc()
    assert "VERSION" in rc
    assert sections(path) == ["VERSION"]
    assert "# [USER]" in path.read_text()


def test_old_format_upgraded(home):
    path = home / ".seamm.d" / "seammrc"
    path.write_text("[dev]\nuser = someone\n")
    rc = SEAMMrc()
    assert rc.get("Dashboard: dev", "user") == "someone"
    assert sections(path) == ["Dashboard: dev", "VERSION"]


def test_set_saves_and_keeps_the_mode(home):
    path = home / ".seamm.d" / "seammrc"
    path.write_text(CONTENT)
    path.chmod(0o600)
    rc = SEAMMrc()
    rc.set("Dashboard: dev", "user", "another")
    config = configparser.ConfigParser()
    config.read(path)
    assert config["Dashboard: dev"]["user"] == "another"
    assert config["Dashboard: dev"]["password"] == "secret"
    assert path.stat().st_mode & 0o777 == 0o600


def test_singleton_takes_a_path(home):
    """SEAMMrc(path) raised TypeError (the arguments went to object.__new__)."""
    path = home / "elsewhere"
    path.write_text(CONTENT)
    assert SEAMMrc(path).get("Dashboard: dev", "user") == "someone"
