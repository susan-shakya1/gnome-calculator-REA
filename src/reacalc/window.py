"""Main window.

Structure follows math-window.ui: a raised AdwToolbarView, a mode menu button
as the header title, undo on the left, primary menu on the right, and an
AdwClamp holding the history/display card above the button panel.

The button panel is the app's own buttons-basic.ui, loaded verbatim, so the
`cal.*` actions below are the exact action names its buttons reference.
"""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib  # noqa: E402

from . import equation  # noqa: E402
from .display import MathDisplay  # noqa: E402
from .history import HistoryView  # noqa: E402
from .number import MathError  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

MODES = [
    ("basic", "Basic"),
    ("advanced", "Advanced"),
    ("financial", "Financial"),
    ("programming", "Programming"),
    ("keyboard", "Keyboard"),
    ("conversion", "Conversion"),
]

NUMBER_FORMATS = [
    ("automatic", "_Automatic"),
    ("fixed", "_Fixed"),
    ("scientific", "_Scientific"),
    ("engineering", "_Engineering"),
]


class MathWindow(Adw.ApplicationWindow):
    __gtype_name__ = "MathWindow"

    def __init__(self, application):
        super().__init__(application=application, title="Calculator")
        self.set_default_size(400, 616)
        self.set_size_request(360, 500)

        self._undo_stack = []
        self._result_showing = False

        self._build_actions()
        self._build_ui()
        self._update_undo_sensitivity()

    # -- construction ----------------------------------------------------

    def _build_ui(self):
        toolbar = Adw.ToolbarView(top_bar_style=Adw.ToolbarStyle.RAISED)

        header = Adw.HeaderBar()
        self.mode_button = Gtk.MenuButton(
            menu_model=self._mode_menu(),
            focus_on_click=False,
            always_show_arrow=True,
            can_shrink=True,
            tooltip_text="Mode Selection",
            label="Basic",
        )
        header.set_title_widget(self.mode_button)

        undo_content = Adw.ButtonContent(
            label="_Undo",
            icon_name="edit-undo-symbolic",
            use_underline=True,
            can_shrink=True,
        )
        self.undo_button = Gtk.Button(
            valign=Gtk.Align.CENTER,
            focus_on_click=False,
            action_name="win.undo",
            child=undo_content,
        )
        header.pack_start(self.undo_button)

        header.pack_end(
            Gtk.MenuButton(
                icon_name="open-menu-symbolic",
                receives_default=False,
                menu_model=self._primary_menu(),
                primary=True,
                tooltip_text="Main Menu",
            )
        )
        toolbar.add_top_bar(header)

        # 10*64px buttons + 9*4px spacing + 2*12px margin, as the original.
        clamp = Adw.Clamp(maximum_size=700, tightening_threshold=700)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)

        display_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, overflow=Gtk.Overflow.HIDDEN
        )
        display_box.add_css_class("card")
        display_box.add_css_class("display-container")

        self.history = HistoryView()
        self.history.set_overflow(Gtk.Overflow.HIDDEN)
        self.history.connect("equation-clicked", self._on_history_equation)
        self.history.connect("answer-clicked", self._on_history_answer)
        display_box.append(self.history)

        self.display = MathDisplay()
        self.display.connect("activate", lambda _w: self._solve())
        display_box.append(self.display)
        box.append(display_box)

        box.append(self._load_button_panel())
        clamp.set_child(box)

        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(clamp)
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)

        self.display.grab_display_focus()

    def _load_button_panel(self):
        builder = Gtk.Builder()
        builder.add_from_file(str(DATA_DIR / "buttons-basic.ui"))
        return builder.get_object("button_panel")

    def _mode_menu(self):
        menu = Gio.Menu()
        section = Gio.Menu()
        for target, label in MODES:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("win.mode", GLib.Variant("s", target))
            section.append_item(item)
        menu.append_section(None, section)
        return menu

    def _primary_menu(self):
        menu = Gio.Menu()

        window_section = Gio.Menu()
        window_section.append("_New Window", "app.new-window")
        menu.append_section(None, window_section)

        clear_section = Gio.Menu()
        clear_section.append("_Clear History", "win.clear")
        menu.append_section(None, clear_section)

        format_section = Gio.Menu()
        for target, label in NUMBER_FORMATS:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(
                "win.number-format", GLib.Variant("s", target)
            )
            format_section.append_item(item)
        menu.append_section("Result Format", format_section)

        help_section = Gio.Menu()
        help_section.append("Keyboard Shortcuts", "win.show-help-overlay")
        help_section.append("About Calculator", "app.about")
        menu.append_section(None, help_section)

        return menu

    def _build_actions(self):
        # Buttons from buttons-basic.ui address the "cal" group.
        calc = Gio.SimpleActionGroup()

        def add(name, handler, parameter_type=None):
            action = Gio.SimpleAction.new(
                name, GLib.VariantType.new(parameter_type) if parameter_type else None
            )
            action.connect("activate", handler)
            calc.add_action(action)
            return action

        add("insert-digit", self._on_insert_digit, "i")
        add("insert-general", self._on_insert_general, "s")
        add("insert-numeric-point", self._on_insert_point)
        add("subtract", self._on_subtract)
        add("square", self._on_square)
        add("clear", self._on_clear)
        add("solve", self._on_solve)
        self.insert_action_group("cal", calc)

        self.undo_action = Gio.SimpleAction.new("undo", None)
        self.undo_action.connect("activate", self._on_undo)
        self.add_action(self.undo_action)

        self.clear_history_action = Gio.SimpleAction.new("clear", None)
        self.clear_history_action.connect("activate", self._on_clear_history)
        self.add_action(self.clear_history_action)

        mode = Gio.SimpleAction.new_stateful(
            "mode", GLib.VariantType.new("s"), GLib.Variant("s", "basic")
        )
        mode.connect("activate", self._on_mode)
        self.add_action(mode)

        number_format = Gio.SimpleAction.new_stateful(
            "number-format", GLib.VariantType.new("s"), GLib.Variant("s", "automatic")
        )
        number_format.connect("activate", self._on_number_format)
        self.add_action(number_format)

        shortcuts = Gio.SimpleAction.new("show-help-overlay", None)
        shortcuts.connect("activate", self._on_shortcuts)
        self.add_action(shortcuts)

    # -- editing ---------------------------------------------------------

    def _push_undo(self):
        self._undo_stack.append(self.display.text)
        self._update_undo_sensitivity()

    def _update_undo_sensitivity(self):
        self.undo_action.set_enabled(bool(self._undo_stack))

    def _insert(self, text, is_digit=False):
        self._push_undo()
        # After `=`, a digit starts a new calculation while an operator
        # continues from the result.
        if self._result_showing and is_digit:
            self.display.text = ""
        self._result_showing = False
        self.display.set_info("")
        self.display.text = self.display.text + text

    def _on_insert_digit(self, _action, value):
        self._insert(str(value.get_int32()), is_digit=True)

    def _on_insert_general(self, _action, value):
        self._insert(value.get_string())

    def _on_insert_point(self, _action, _param):
        self._insert(".", is_digit=True)

    def _on_subtract(self, _action, _param):
        self._insert("−")

    def _on_square(self, _action, _param):
        self._insert("²")

    def _on_clear(self, _action, _param):
        self._push_undo()
        self._result_showing = False
        self.display.text = ""
        self.display.set_info("")

    def _on_solve(self, _action, _param):
        self._solve()

    def _solve(self):
        text = self.display.text.strip()
        if not text:
            return
        try:
            result = equation.solve(text)
        except MathError as exc:
            self.display.set_info(str(exc) or "Malformed expression")
            return

        self.history.add(text, result)
        self._push_undo()
        self.display.text = result
        self.display.set_info("")
        self._result_showing = True
        self.clear_history_action.set_enabled(True)

    def _on_undo(self, _action, _param):
        if not self._undo_stack:
            return
        self.display.text = self._undo_stack.pop()
        self.display.set_info("")
        self._result_showing = False
        self._update_undo_sensitivity()

    # -- history ---------------------------------------------------------

    def _on_history_equation(self, _view, text):
        self._push_undo()
        self._result_showing = False
        self.display.text = text

    def _on_history_answer(self, _view, text):
        self._insert(text)

    def _on_clear_history(self, _action, _param):
        self.history.clear()
        self.clear_history_action.set_enabled(False)

    # -- menus -----------------------------------------------------------

    def _on_mode(self, action, value):
        target = value.get_string()
        if target != "basic":
            label = dict(MODES)[target]
            self.toasts.add_toast(
                Adw.Toast.new(f"{label} mode is not part of this recreation")
            )
            return
        action.set_state(value)

    def _on_number_format(self, action, value):
        if value.get_string() != "automatic":
            self.toasts.add_toast(
                Adw.Toast.new("Only the automatic result format is implemented")
            )
            return
        action.set_state(value)

    def _on_shortcuts(self, _action, _param):
        self.toasts.add_toast(
            Adw.Toast.new("Keyboard: digits, + - * / ( ) %, Enter to solve, Esc to clear")
        )
