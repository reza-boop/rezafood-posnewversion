from __future__ import annotations

import pytest

import launcher


class TestChooseMode:
    def test_auto_uses_desktop_when_supported(self, monkeypatch):
        monkeypatch.setattr(launcher, "_tkinter_available", lambda: True)
        monkeypatch.setattr(launcher, "_has_graphical_display", lambda: True)

        mode, reason = launcher.choose_mode()

        assert mode == "desktop"
        assert reason is None

    def test_auto_falls_back_to_web_without_tkinter(self, monkeypatch):
        monkeypatch.setattr(launcher, "_tkinter_available", lambda: False)
        monkeypatch.setattr(launcher, "_has_graphical_display", lambda: True)

        mode, reason = launcher.choose_mode()

        assert mode == "web"
        assert reason == "Tkinter is not installed in this Python environment."

    def test_auto_falls_back_to_web_without_display(self, monkeypatch):
        monkeypatch.setattr(launcher, "_tkinter_available", lambda: True)
        monkeypatch.setattr(launcher, "_has_graphical_display", lambda: False)

        mode, reason = launcher.choose_mode()

        assert mode == "web"
        assert reason == "No graphical desktop session was detected."

    def test_invalid_mode_raises_value_error(self):
        with pytest.raises(ValueError):
            launcher.choose_mode("nope")


class TestMain:
    def test_main_runs_web_when_auto_falls_back(self, monkeypatch):
        called = {"desktop": 0, "web": 0}

        monkeypatch.setattr(
            launcher,
            "choose_mode",
            lambda preferred_mode=None: (
                "web",
                "Tkinter is not installed in this Python environment.",
            ),
        )
        monkeypatch.setattr(
            launcher,
            "_run_desktop",
            lambda: called.__setitem__("desktop", called["desktop"] + 1),
        )
        monkeypatch.setattr(
            launcher,
            "_run_web",
            lambda: called.__setitem__("web", called["web"] + 1),
        )

        launcher.main([])

        assert called == {"desktop": 0, "web": 1}

    def test_main_exits_when_desktop_is_forced_but_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            launcher,
            "choose_mode",
            lambda preferred_mode=None: (
                "desktop",
                "Tkinter is not installed in this Python environment.",
            ),
        )

        with pytest.raises(SystemExit):
            launcher.main(["--desktop"])
