"""The equation display: editable expression line plus an info/error line.

Structure mirrors the app's math-display.ui. The real app uses GtkSourceView;
the Python bindings for it are not present, so a GtkTextView carries the same
`.sourceview` style class instead.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, GObject  # noqa: E402


class MathDisplay(Gtk.Box):
    __gtype_name__ = "MathDisplay"

    __gsignals__ = {
        "activate": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("mathdisplay")

        self.scrolled = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        self.scrolled.add_css_class("display-scrolled")

        self.view = Gtk.TextView(
            accepts_tab=False,
            left_margin=14,
            right_margin=14,
            pixels_above_lines=8,
            pixels_below_lines=2,
            justification=Gtk.Justification.LEFT,
            width_request=20,
            height_request=45,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
        )
        self.view.add_css_class("sourceview")
        self.buffer = self.view.get_buffer()
        self.scrolled.set_child(self.view)
        self.append(self.scrolled)

        info_box = Gtk.Box(spacing=6)
        self.info_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD,
            can_focus=False,
            editable=False,
            left_margin=12,
            right_margin=12,
            hexpand=True,
        )
        self.info_view.add_css_class("info-view")
        info_box.append(self.info_view)
        self.append(info_box)

        controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        controller.connect("key-pressed", self._on_key_pressed)
        self.view.add_controller(controller)

    @property
    def text(self):
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, False)

    @text.setter
    def text(self, value):
        self.buffer.set_text(value)
        self.scroll_to_end()

    def scroll_to_end(self):
        self.buffer.place_cursor(self.buffer.get_end_iter())
        self.view.scroll_to_mark(self.buffer.get_insert(), 0.0, False, 0.0, 0.0)

    def set_info(self, message):
        self.info_view.get_buffer().set_text(message or "")

    def grab_display_focus(self):
        self.view.grab_focus()

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        from gi.repository import Gdk

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_equal):
            self.emit("activate")
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE
