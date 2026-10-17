# rea-calc

A recreation of **GNOME Calculator 48.1** (Basic mode), rebuilt by reverse
engineering the installed binary rather than reading upstream source.

Built with GTK4 + libadwaita via PyGObject, so it renders through the same
toolkit as the original and loads the original's own UI definitions.

```sh
./run.sh                 # launch the app
./run.sh -s "2+3×4"      # solve from the command line, like the original
```

## Documentation

| | |
|---|---|
| **[How it was built](docs/HOW-IT-WAS-BUILT.md)** | The full method: reading the architecture off `ldd`, extracting the embedded GResource bundle, using the binary's own solver as a test oracle, and verifying the result. |
| **[What REA is](docs/REA.md)** | What the REA project does, how it is put together, and an honest account of why it contributed nothing to this build. |

## How faithful is it

The app does not imitate the original's interface — it **loads it**.

- `data/buttons-basic.ui` is the file extracted from the binary, **verbatim**.
  Every label, tooltip, style class, grid position and action name is the
  original's.
- `data/style.css` is the original stylesheet, with one documented selector
  change (see Deviations).
- The arithmetic engine matches the real one on **60/60** expressions,
  compared as output strings so rounding, notation and error wording all count.

All 17 resources recovered from the binary are in [`reference/`](reference/),
unmodified, including the button definitions for the five modes not built.

## Verification

```sh
python3 tests/differential.py                      # 60/60 vs the real binary
python3 tests/screenshot.py out.png "7*8=100/3="   # render a UI state to PNG
```

`differential.py` runs every expression through both this engine and
`gnome-calculator -s`, and compares the formatted output strings. A difference
in rounding, scientific notation, the Unicode minus sign or an error message
fails the test.

`screenshot.py` renders through the app's own GSK renderer, because the Wayland
compositor denies external screenshot requests. It can drive a button sequence
before capturing.

## Layout

The Basic grid, exactly as `buttons-basic.ui` defines it:

| | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| **0** | C | ( | ) | mod | π |
| **1** | 7 | 8 | 9 | ÷ | √ |
| **2** | 4 | 5 | 6 | × | x² |
| **3** | 1 | 2 | 3 | − | = |
| **4** | 0 | . | % | + | ↑ |

## Deviations from the original

- **Basic mode only.** Advanced, Financial, Programming, Keyboard and
  Conversion appear in the mode menu but show a toast. Their button
  definitions are already in `reference/`; see the end of
  [How it was built](docs/HOW-IT-WAS-BUILT.md#extending-this).
- **`GtkTextView` instead of `GtkSourceView`.** The GtkSource 5 Python
  bindings are not installed; the display carries the same `.sourceview` class.
- **One CSS selector changed.** Upstream targets the `mathdisplay` CSS *node
  name*; PyGObject widgets inherit their parent's node name, so those rules
  are class selectors in `data/style.css`. Unmodified original in
  `reference/style.css`.
- **No complex numbers.** The real app does `√(−4)` → `2i` via MPC. Here that
  is an error.
- **Result format** is always automatic; fixed, scientific and engineering are
  not implemented.
- **No persistence.** The original stores history and settings via GSettings.

## Repo layout

```
data/        UI and stylesheet loaded at runtime
docs/        How it was built, and what REA is
reference/   All 17 resources extracted from the binary, unmodified
src/reacalc/ number.py (formatting), equation.py (parser), window/display/history
tests/       differential.py (oracle comparison), screenshot.py (render capture)
```

## Legal

GNOME Calculator is GPL-3.0 free software, installed from the Debian archive.
Analysing software you own or are authorised to examine is permitted; its
source is public in any case. It was reverse engineered here as an exercise,
deliberately without reading that source.
