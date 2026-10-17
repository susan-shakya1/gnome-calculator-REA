# How this app was built

A walkthrough of reverse engineering GNOME Calculator 48.1 and rebuilding its
Basic mode. Written so the method transfers to other targets, not just this one.

The guiding constraint: **rebuild from the compiled artifact, not from upstream
source.** GNOME Calculator is GPL and its Vala source is a click away — reading
it would have been faster and was deliberately avoided, because the exercise is
the reverse engineering.

---

## Phase 0 — Identify the target

```sh
which gnome-calculator                  # /usr/bin/gnome-calculator
gnome-calculator --version              # 48.1
file /usr/bin/gnome-calculator          # ELF 64-bit LSB pie, x86-64, stripped
dpkg -l | grep gnome-calculator         # 1:48.1-2+b1, Debian
```

Stripped, 795 KB. No symbols to lean on.

## Phase 1 — Read the architecture off the link table

Before any deep analysis, `ldd` tells you what kind of program this is. The
libraries a binary links are a design document:

```sh
ldd /usr/bin/gnome-calculator
```

| Library | What it tells you |
|---|---|
| `libgtk-4`, `libadwaita-1` | GTK4 + libadwaita. Modern GNOME. Declarative `.ui` files likely. |
| `libgtksourceview-5` | The display is a source-editor widget, not a plain label. |
| **`libmpfr`, `libmpc`** | **Arbitrary-precision real *and complex* arithmetic.** Not IEEE doubles. |
| `libsoup-3`, `libxml2` | HTTP + XML — currency conversion fetches live rates. |

That MPFR/MPC line is the single most valuable early finding. It predicts that
`0.1+0.2` will be exactly `0.3` and that `√(−4)` will return `2i` — both later
confirmed. It also rules out implementing the engine with floats.

**Transferable:** always run `ldd` first. Five seconds, and it frames
everything after.

## Phase 2 — Extract the embedded resources

This is where the project was effectively won.

GTK applications compile their UI definitions, stylesheets and icons into a
**GResource** bundle linked into the executable. It is not obfuscated, and
`gresource` reads it directly:

```sh
gresource list /usr/bin/gnome-calculator
```

```
/org/gnome/calculator/buttons-advanced.ui
/org/gnome/calculator/buttons-basic.ui
/org/gnome/calculator/buttons-conversion.ui
/org/gnome/calculator/buttons-financial.ui
/org/gnome/calculator/buttons-programming.ui
/org/gnome/calculator/gtk/help-overlay.ui
/org/gnome/calculator/history-entry.ui
/org/gnome/calculator/history-view.ui
/org/gnome/calculator/math-converter.ui
/org/gnome/calculator/math-display.ui
/org/gnome/calculator/math-function-popover.ui
/org/gnome/calculator/math-preferences.ui
/org/gnome/calculator/math-variable-popover.ui
/org/gnome/calculator/math-window.ui
/org/gnome/calculator/style-dark.css
/org/gnome/calculator/style-hc.css
/org/gnome/calculator/style.css
```

Extract every one:

```sh
for r in $(gresource list /usr/bin/gnome-calculator); do
  gresource extract /usr/bin/gnome-calculator "$r" > "reference/$(basename "$r")"
done
```

These are in [`../reference/`](../reference/), unmodified.

**What this means.** These are not reconstructions. They are the exact XML and
CSS the GNOME developers wrote, recovered byte-for-byte. Every button's label,
tooltip, style class, grid position and action name is now known exactly —
no decompiler could match this fidelity.

From `buttons-basic.ui`, the grid falls straight out of the `<layout>` blocks:

| | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| **0** | C | ( | ) | mod | π |
| **1** | 7 | 8 | 9 | ÷ | √ |
| **2** | 4 | 5 | 6 | × | x² |
| **3** | 1 | 2 | 3 | − | = *(row-span 2)* |
| **4** | 0 | . | % | + | |

Along with the action names each button fires — `cal.insert-digit` with an
int32 target, `cal.insert-general` with a string, plus `cal.subtract`,
`cal.square`, `cal.clear`, `cal.solve`. Implementing those exact names meant
`buttons-basic.ui` could be loaded **verbatim** at runtime. It is the original
file; `data/buttons-basic.ui` is a straight copy.

`math-window.ui` gave the window shell (AdwToolbarView, raised header, mode
menu button as title, `AdwClamp` at 700px) and `style.css` gave every
dimension — `min-height: calc(44px * 5 + 4px * 4)` for the grid, `4px` button
spacing, `12px` margins.

## Phase 3 — Extract the behaviour

The UI was free. Arithmetic semantics were not — they live in compiled code.
Two sources settled them without decompiling anything.

### 3a. The authoritative settings schema

```sh
gsettings list-recursively org.gnome.calculator
```

```
accuracy         9          ← nine displayed decimal places
precision        2000       ← internal MPFR precision, in bits
number-format    'automatic'
show-zeroes      false      ← strip trailing zeros
show-thousands   false
base             10
word-size        64
angle-units      'degrees'
```

### 3b. The binary as its own oracle

`gnome-calculator --help` revealed the decisive feature:

```
-s, --solve=equation    Solve given equation
```

The real engine is directly queryable from the shell. That converts "what does
this program compute?" from a decompilation problem into an *experiment*:

```sh
gnome-calculator -s "0.1+0.2"        # 0.3
gnome-calculator -s "−7 mod 3"       # 2
gnome-calculator -s "200+10%"        # 220
```

Roughly 60 probes produced the full specification:

| Property | Finding |
|---|---|
| Precision | 9 **decimal places** — not significant figures (`1÷3` → `0.333333333`) |
| Arithmetic | Exact decimal: `0.1+0.2` → `0.3`, never `0.30000000000000004` |
| Trailing zeros | Stripped: `1.50+0.50` → `2` |
| Scientific threshold | At \|x\| ≥ 10¹². `999999999999` plain; `10¹²` → `1×10¹²` |
| Scientific format | Unicode superscripts: `1.219326311×10¹⁷` |
| Underflow | `1÷10000000000` → `0`, *not* scientific notation |
| Minus sign | U+2212 `−`, not ASCII hyphen |
| Modulo | Mathematical, not truncated: `−7 mod 3` → `2` (C would give −1) |
| Percent | Contextual: `50%`→`0.5`, `200+10%`→`220`, `200×10%`→`20` |
| Superscripts | Postfix exponent: `9²+1` → `82` |
| `e` | Euler's number. `1e100` is *not* scientific input — it errors |
| Negative roots | `(−8)^(1÷3)` → `−2`, the real root, not the complex principal |
| Complex | `√(−4)` → `2i` (MPC) — **not reimplemented here** |
| Division by zero | `Error: Division by zero is undefined` |

Several of these are things you would never guess. Contextual percent and
mathematical modulo in particular are choices, not consequences.

**Transferable:** before decompiling, check what the target exposes. A CLI
mode, a debug flag, a scripting API, an accessibility tree — any of them turns
guesswork into measurement.

## Phase 4 — Choosing the rebuild stack

With GTK4 and libadwaita already on the machine and PyGObject bindings
present, the choice made itself:

```sh
python3 -c "import gi; gi.require_version('Gtk','4.0'); ..."
# GTK 4.18.6, libadwaita 1.7
```

Rebuilding in the **same toolkit** means the extracted `.ui` and `.css` are
not a reference to imitate — they are the actual inputs. Pixel fidelity stops
being an effort and becomes a property of the approach. A web reimplementation
would have meant hand-approximating every one of those measurements.

One caveat found immediately: the GTK4 bindings live on `/usr/bin/python3`,
not the pyenv shim on `PATH`. Hence `run.sh` hardcodes the interpreter.

## Phase 5 — Implementation

| Module | Role |
|---|---|
| `number.py` | `Decimal` arithmetic at 80 digits; the display serializer |
| `equation.py` | Tokenizer, recursive-descent parser, evaluator |
| `display.py` | `MathDisplay`, mirroring `math-display.ui` |
| `history.py` | `HistoryView` / `HistoryEntry`, mirroring their `.ui` files |
| `window.py` | Window shell; registers the `cal.*` actions the buttons call |
| `application.py` | `Adw.Application`, CSS loading, `-s` solve mode |

Notes on the non-obvious parts:

**Exact decimals.** Python's `decimal` at `prec=80` reproduces MPFR's observed
behaviour at nine displayed places. `float` would fail the very first test.

**Percent is a parse node, not a value.** Because `200+10%` is 220 but
`200×10%` is 20, `%` cannot be folded during evaluation. It becomes a `Percent`
node; a binary `+`/`−` sees it on its right and computes a share of the left
operand, while every other context treats it as a hundredth.

**Modulo for free.** `−7 mod 3` → `2` is exactly Python's `%` semantics, so
`number.modulus` uses floor division rather than C-style truncation.

**`run.sh -s` was kept.** Mirroring the oracle interface makes the two engines
comparable from the shell, which is what makes the differential test cheap.

## Phase 6 — Verification

### Differential testing against the real binary

The binary is the specification, so the test suite asks it:

```sh
python3 tests/differential.py      # 60/60 exact match
```

For each expression it runs both engines and compares **output strings**, not
numbers — so rounding, notation, Unicode minus and error wording are all in
scope. `0.333333333` vs `0.3333333333` fails. `-5` vs `−5` fails.

This caught two real bugs that review had not:

1. **Double-inverted exponent.** `(−8)^(1÷3)` returned `−512` instead of `−2`.
   The negative-base branch reciprocated an exponent that was already a
   reciprocal.
2. **`str.isdigit()` is true for superscripts.** `"²".isdigit()` → `True` in
   Python, so the number scanner swallowed `9²` as one token and `Decimal`
   choked. Fixed with an explicit ASCII range check.

The second is the better lesson: it only surfaced because `9²+1` was added to
the corpus *after* the suite was already green. **A differential suite is only
as good as its corpus** — extend it before trusting any engine change.

### Visual verification

The Wayland compositor denies external screenshots — `org.gnome.Shell.Screenshot`
returns `AccessDenied` and `Shell.Eval` is locked down. The workaround is to
render from *inside* the process using the app's own GSK renderer:

```
Gtk.WidgetPaintable → Gtk.Snapshot → renderer.render_texture() → save_to_png()
```

```sh
python3 tests/screenshot.py out.png "7*8=100/3="
```

It can drive a button sequence first, so UI states are reproducible without a
compositor, a display grab or any manual clicking.

### Bugs the tests did not catch

Two were found by reasoning rather than testing, worth recording:

- **`run(None)`** did not pick up `sys.argv`, so `-s` silently produced no
  output while exiting 0. Fixed by passing `sys.argv` explicitly.
- **Double-solve.** `Return` was bound both as an accelerator on `cal.solve`
  and in the display's key controller — one press would have produced two
  history entries. The accelerator was removed; upstream handles the key in
  the controller too.

## What REA contributed

Nothing usable, and the reasons are instructive rather than embarrassing.
Full account in [REA.md](REA.md). Short version: REA brokers other tools, and
the tools it needed (Ghidra/Hopper/IDA, pwntools) were absent, while its UI
capture wants an X11-style window ID that Wayland does not provide.

It would not have helped much regardless. Decompiling Vala-generated C to
recover a button grid is strictly worse than `gresource extract` returning the
original XML.

## Extending this

The five unimplemented modes already have their complete button definitions in
[`../reference/`](../reference/) — `buttons-advanced.ui`, `buttons-financial.ui`,
`buttons-programming.ui`, `buttons-conversion.ui`. Adding Advanced mode is
mostly wiring:

1. Load `reference/buttons-advanced.ui` the way `window.py` loads the basic panel.
2. Add the `cal.*` actions its buttons name that do not exist yet.
3. Extend `equation.py` with the functions (`sin`, `cos`, `ln`, `log`, …).
4. **Add every new case to `tests/differential.py` first** and let the real
   binary tell you what each should return.

Step 4 is the method in one line. The oracle is still installed; keep asking it.
