"""Scrolling history list above the display.

Mirrors history-view.ui and history-entry.ui: each row is an ellipsized
equation, a dimmed `=`, and a bold answer, both halves clickable.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GObject, Pango  # noqa: E402


class HistoryEntry(Gtk.ListBoxRow):
    __gtype_name__ = "HistoryEntry"

    __gsignals__ = {
        "equation-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "answer-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, equation, answer):
        super().__init__()
        self.equation = equation
        self.answer = answer
        self.add_css_class("history-entry")

        grid = Gtk.Grid(margin_start=12, margin_end=16, column_homogeneous=True)

        self.equation_label = Gtk.Label(
            label=equation,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=0.0,
            yalign=0.5,
            max_width_chars=1,
        )
        self.equation_label.add_css_class("equation-label")
        grid.attach(self.equation_label, 0, 0, 4, 1)

        symbol = Gtk.Label(label="=", xalign=0.5, yalign=0.5, max_width_chars=1)
        symbol.add_css_class("equation-symbol")
        symbol.add_css_class("dimmed")
        grid.attach(symbol, 4, 0, 1, 1)

        self.answer_label = Gtk.Label(
            label=answer,
            ellipsize=Pango.EllipsizeMode.END,
            xalign=1.0,
            yalign=0.5,
            max_width_chars=12,
        )
        self.answer_label.add_css_class("answer-label")
        self.answer_label.set_attributes(_bold())
        grid.attach(self.answer_label, 5, 0, 2, 1)

        self.set_child(grid)

        self._add_click(self.equation_label, "equation-clicked", equation)
        self._add_click(self.answer_label, "answer-clicked", answer)

    def _add_click(self, widget, signal, payload):
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", lambda *_: self.emit(signal, payload))
        widget.add_controller(gesture)


def _bold():
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
    return attrs


class HistoryView(Adw.Bin):
    __gtype_name__ = "HistoryView"

    __gsignals__ = {
        "equation-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "answer-clicked": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.scrolled = Gtk.ScrolledWindow(
            vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER
        )
        self.scrolled.add_css_class("history-view")

        self.listbox = Gtk.ListBox(
            vexpand=True,
            valign=Gtk.Align.END,
            selection_mode=Gtk.SelectionMode.NONE,
        )
        viewport = Gtk.Viewport(hexpand=True, scroll_to_focus=True)
        viewport.set_child(self.listbox)
        self.scrolled.set_child(viewport)
        self.set_child(self.scrolled)

    @property
    def is_empty(self):
        return self.listbox.get_first_child() is None

    def add(self, equation, answer):
        entry = HistoryEntry(equation, answer)
        entry.connect("equation-clicked", lambda _w, t: self.emit("equation-clicked", t))
        entry.connect("answer-clicked", lambda _w, t: self.emit("answer-clicked", t))
        self.listbox.append(entry)
        self._scroll_to_bottom()

    def clear(self):
        while (child := self.listbox.get_first_child()) is not None:
            self.listbox.remove(child)

    def _scroll_to_bottom(self):
        from gi.repository import GLib

        def scroll():
            adjustment = self.scrolled.get_vadjustment()
            adjustment.set_value(
                adjustment.get_upper() - adjustment.get_page_size()
            )
            return GLib.SOURCE_REMOVE

        GLib.idle_add(scroll)
