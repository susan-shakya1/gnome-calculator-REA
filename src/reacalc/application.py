"""Application object, stylesheet loading and global shortcuts."""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, Gdk  # noqa: E402

from .window import MathWindow  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
APP_ID = "org.example.ReaCalc"


class ReaCalcApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._add_actions()

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._load_css()
        self.set_accels_for_action("win.undo", ["<Control>z"])
        self.set_accels_for_action("cal.clear", ["Escape"])
        # Return is handled by the display's key controller, as upstream does,
        # so it must not also be bound here or a press would solve twice.

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if "-s" in args or "--solve" in args:
            from . import equation
            from .number import MathError

            index = args.index("-s" if "-s" in args else "--solve")
            if index + 1 < len(args):
                try:
                    print(equation.solve(args[index + 1]), flush=True)
                except MathError as exc:
                    print(f"Error: {exc}" if str(exc) else "Error", flush=True)
            return 0
        self.activate()
        return 0

    def do_activate(self):
        MathWindow(self).present()

    def _add_actions(self):
        new_window = Gio.SimpleAction.new("new-window", None)
        new_window.connect("activate", lambda *_: MathWindow(self).present())
        self.add_action(new_window)

        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", self._on_about)
        self.add_action(about)

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_path(str(DATA_DIR / "style.css"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _on_about(self, *_args):
        dialog = Adw.AboutDialog(
            application_name="Calculator",
            application_icon="accessories-calculator",
            developer_name="rea-calc",
            version="0.1.0",
            comments=(
                "A recreation of GNOME Calculator 48.1 Basic mode, rebuilt from "
                "the shipped binary's embedded resources and its measured "
                "arithmetic behaviour."
            ),
            license_type=Gtk.License.GPL_3_0,
        )
        dialog.present(self.get_active_window())


def main():
    import sys

    return ReaCalcApplication().run(sys.argv)
