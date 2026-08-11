#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for dashboard_handler.py's TLS "verify" support.

Added for a real dashboard: seamm_webui generates a self-signed
certificate for a non-loopback bind (its tls.py) -- without a way to tell
a dashboard to trust that specific certificate, connecting to it over
https fails with a hard SSL verification error (requests' own default).
"""

import configparser

import pytest  # noqa: F401

from seamm.dashboard_handler import DashboardHandler, _parse_verify

# --- _parse_verify: pure function, no side effects -------------------------


def test_parse_verify_blank_defaults_true():
    assert _parse_verify("") is True
    assert _parse_verify(None) is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "No", "0"])
def test_parse_verify_false_values(value):
    assert _parse_verify(value) is False


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "Yes", "1"])
def test_parse_verify_true_values(value):
    assert _parse_verify(value) is True


def test_parse_verify_path_passes_through():
    assert _parse_verify("/path/to/webui.crt") == "/path/to/webui.crt"


def test_parse_verify_expands_user():
    import os

    home = os.path.expanduser("~")
    assert _parse_verify("~/webui.crt") == f"{home}/webui.crt"


# --- DashboardHandler.add_dashboard / get_dashboard -------------------------


def _bare_handler(tmp_path, monkeypatch):
    """A DashboardHandler with no real filesystem/credentials touched --
    bypasses __init__ (which reads seamm_util's global options and
    ~/.seamm.d/seammrc) and wires up just what add_dashboard/get_dashboard
    need, pointed at an isolated tmp_path config.

    get_credentials is stubbed unconditionally (not just around individual
    get_dashboard() calls): the current_dashboard property auto-selects a
    "current" dashboard via get_dashboard() the moment nothing is selected
    yet, and save_configuration() (called by both add_dashboard and
    update) reads that property -- so it can fire from inside a plain
    add_dashboard() call too, not only an explicit get_dashboard()."""
    dh = DashboardHandler.__new__(DashboardHandler)
    dh.config = configparser.ConfigParser()
    dh.configfile = tmp_path / "dashboards.ini"
    dh.user_agent = "test-agent"
    dh._current_dashboard = None
    monkeypatch.setattr(dh, "get_credentials", lambda name, ask=None: (None, None))
    return dh


def test_add_dashboard_stores_verify(tmp_path, monkeypatch):
    dh = _bare_handler(tmp_path, monkeypatch)
    dh.add_dashboard("molssi10", "https://molssi10.molssi.org:55060", "https", "/x.crt")

    assert dh.config["molssi10"]["verify"] == "/x.crt"


def test_add_dashboard_verify_defaults_blank(tmp_path, monkeypatch):
    dh = _bare_handler(tmp_path, monkeypatch)
    dh.add_dashboard("dev", "http://localhost:55066", "http")

    assert dh.config["dev"]["verify"] == ""


def test_get_dashboard_passes_parsed_verify_to_client(tmp_path, monkeypatch):
    dh = _bare_handler(tmp_path, monkeypatch)
    dh.add_dashboard("molssi10", "https://molssi10.molssi.org:55060", "https", "/x.crt")

    dashboard = dh.get_dashboard("molssi10")

    assert dashboard.verify == "/x.crt"
    assert dashboard.url == "https://molssi10.molssi.org:55060"


def test_get_dashboard_no_verify_key_defaults_true(tmp_path, monkeypatch):
    dh = _bare_handler(tmp_path, monkeypatch)
    dh.add_dashboard("dev", "http://localhost:55066", "http")

    dashboard = dh.get_dashboard("dev")

    assert dashboard.verify is True


def test_update_round_trips_bool_verify(tmp_path, monkeypatch):
    dh = _bare_handler(tmp_path, monkeypatch)
    dh.add_dashboard("dev", "http://localhost:55066", "http")

    dashboard = dh.get_dashboard("dev")
    assert dashboard.verify is True

    dh.update(dashboard)
    assert dh.config["dev"]["verify"] == "True"

    reloaded = dh.get_dashboard("dev")
    assert reloaded.verify is True
