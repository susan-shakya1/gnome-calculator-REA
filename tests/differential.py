"""Differential test: our engine vs the real gnome-calculator.

Runs each expression through `gnome-calculator -s` and through our engine,
and reports any divergence. The real binary is the oracle.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reacalc import equation  # noqa: E402
from reacalc.number import MathError  # noqa: E402

CASES = [
    "1+2",
    "1÷3",
    "2÷3",
    "10÷3",
    "1÷7",
    "π",
    "√2",
    "√16",
    "2+3×4",
    "(2+3)×4",
    "100−1",
    "7 mod 3",
    "−7 mod 3",
    "50%",
    "200+10%",
    "200−10%",
    "200×10%",
    "200÷10%",
    "1÷0",
    "2^10",
    "2^0.5",
    "123456789×987654321",
    "0.1+0.2",
    "1000000000000×1",
    "999999999999×1",
    "1234567890123×1",
    "1÷1000",
    "1÷10000000000",
    "4÷2",
    "1.50+0.50",
    "2.0×3.0",
    "1÷4",
    "0−5",
    "5!",
    "|0−7|",
    "10^3",
    "3.14×2",
    "(1+2)×(3+4)",
    "100÷3×3",
    "π×2",
    "√2×√2",
    "2^10÷2",
    "0.5+0.25",
    "1−0.9",
    "(0−8)^(1÷3)",
    "12%×100",
    "9÷3+1",
    "2×3^2",
    # Superscript exponents, as the x² button inserts.
    "2²",
    "3²",
    "2³",
    "9²+1",
    "2²×3",
    "√9²",
    "10²÷4",
    "e",
    "e×2",
    "π²",
    "0.5²",
    "(2+3)²",
]


def real(expr):
    try:
        out = subprocess.run(
            ["gnome-calculator", "-s", expr],
            capture_output=True, text=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        return "<timeout>"
    return out.stdout.strip() or out.stderr.strip()


def ours(expr):
    try:
        return equation.solve(expr)
    except MathError as exc:
        return f"Error: {exc}" if str(exc) else "Error"
    except Exception as exc:  # noqa: BLE001
        return f"<crash: {type(exc).__name__}: {exc}>"


def main():
    passed = failed = 0
    failures = []
    for expr in CASES:
        expected = real(expr)
        actual = ours(expr)
        if expected == actual:
            passed += 1
        else:
            failed += 1
            failures.append((expr, expected, actual))

    for expr, expected, actual in failures:
        print(f"DIFF  {expr}\n      real: {expected!r}\n      ours: {actual!r}")

    print(f"\n{passed} match, {failed} differ, {len(CASES)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
