"""Render the window to a PNG from inside the process.

The Wayland compositor denies external screenshot requests, so this uses the
app's own GSK renderer instead. Optionally drives a key sequence first:

    python3 tests/screenshot.py out.png "123+456="
"""

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gsk  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reacalc.application import ReaCalcApplication  # noqa: E402
from reacalc.window import MathWindow  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("window.png")
SEQUENCE = sys.argv[2] if len(sys.argv) > 2 else ""

ACTIONS = {
    "+": ("cal.insert-general", "+"),
    "−": ("cal.subtract", None),
    "-": ("cal.subtract", None),
    "×": ("cal.insert-general", "×"),
    "*": ("cal.insert-general", "×"),
    "÷": ("cal.insert-general", "÷"),
    "/": ("cal.insert-general", "÷"),
    "(": ("cal.insert-general", "("),
    ")": ("cal.insert-general", ")"),
    "%": ("cal.insert-general", "%"),
    "π": ("cal.insert-general", "π"),
    "√": ("cal.insert-general", "√"),
    ".": ("cal.insert-numeric-point", None),
    "=": ("cal.solve", None),
    "C": ("cal.clear", None),
}


def drive(window, sequence):
    for char in sequence:
        if char.isdigit():
            window.activate_action("cal.insert-digit", GLib.Variant("i", int(char)))
        elif char in ACTIONS:
            name, payload = ACTIONS[char]
            window.activate_action(
                name, GLib.Variant("s", payload) if payload is not None else None
            )


def capture(window):
    width = window.get_width()
    height = window.get_height()
    if width <= 0 or height <= 0:
        return False

    paintable = Gtk.WidgetPaintable.new(window)
    snapshot = Gtk.Snapshot()
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()
    if node is None:
        return False

    texture = window.get_native().get_renderer().render_texture(node, None)
    texture.save_to_png(str(OUT))
    print(f"wrote {OUT} ({width}x{height})")
    return True


class Shot(ReaCalcApplication):
    def do_activate(self):
        window = MathWindow(self)
        window.present()

        attempts = [0]

        def step_drive():
            drive(window, SEQUENCE)
            GLib.timeout_add(300, step_capture)
            return GLib.SOURCE_REMOVE

        def step_capture():
            attempts[0] += 1
            if capture(window):
                self.quit()
                return GLib.SOURCE_REMOVE
            if attempts[0] > 20:
                print("window never produced a render node", file=sys.stderr)
                self.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(600, step_drive)


if __name__ == "__main__":
    raise SystemExit(Shot().run([]))
