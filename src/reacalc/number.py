"""Decimal number type and display serializer.

Mirrors gnome-calculator 48.1 defaults: accuracy=9, show-zeroes=false,
show-thousands=false, number-format=automatic.
"""

from decimal import Decimal, getcontext, localcontext, InvalidOperation

# gnome-calculator uses MPFR at precision=2000 bits (~600 decimal digits).
# 80 digits is far more than the 9 displayed places need, and keeps
# intermediate rounding invisible at display precision.
getcontext().prec = 80

PI = Decimal(
    "3.14159265358979323846264338327950288419716939937510"
    "58209749445923078164062862089986280348253421170679"
)
E = Decimal(
    "2.71828182845904523536028747135266249775724709369995"
    "95749669676277240766303535475945713821785251664274"
)

ACCURACY = 9
MINUS = "−"  # U+2212 MINUS SIGN, as the real app uses
SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")

# Measured against the real app: 999999999999 prints plain, 10**12 goes
# scientific.
SCIENTIFIC_THRESHOLD = Decimal(10) ** 12


class MathError(Exception):
    """Raised for conditions the real app reports in its info bar."""


def _strip_zeroes(text):
    if "." not in text:
        return text
    text = text.rstrip("0").rstrip(".")
    return text or "0"


def _fixed(value, places=ACCURACY):
    quant = Decimal(1).scaleb(-places)
    with localcontext() as ctx:
        ctx.prec = 80
        rounded = value.quantize(quant)
    sign = MINUS if rounded < 0 else ""
    digits = _strip_zeroes(format(abs(rounded), "f"))
    if digits == "0":
        return "0"
    return sign + digits


def _superscript(exponent):
    return str(exponent).translate(SUPERSCRIPT)


def _scientific(value):
    sign = MINUS if value < 0 else ""
    magnitude = abs(value)
    exponent = magnitude.adjusted()
    mantissa = magnitude.scaleb(-exponent)
    text = _fixed(mantissa)
    return f"{sign}{text}×10{_superscript(exponent)}"


def serialize(value):
    """Format a Decimal the way the real display does."""
    if value.is_nan():
        raise MathError("Result is undefined")
    if value.is_infinite():
        raise MathError("Result is undefined")

    if value == 0:
        return "0"

    if abs(value) >= SCIENTIFIC_THRESHOLD:
        return _scientific(value)

    # Automatic format rounds sub-accuracy magnitudes to zero rather than
    # switching to scientific; 1e-10 displays as "0" in the real app.
    return _fixed(value)


def parse_number(text):
    try:
        return Decimal(text)
    except InvalidOperation:
        raise MathError(f"Malformed number: {text}")


def sqrt(value):
    if value < 0:
        raise MathError("The square root of a negative number is not real")
    return value.sqrt()


def power(base, exponent):
    if base == 0 and exponent < 0:
        raise MathError("Division by zero is undefined")

    if exponent == exponent.to_integral_value() and abs(exponent) < 10**6:
        return base ** int(exponent)

    if base < 0:
        # The real app returns the real cube root for (-8)^(1/3) rather than
        # the complex principal root; same for any odd integer reciprocal.
        inverse = 1 / exponent
        nearest = inverse.to_integral_value()
        if abs(inverse - nearest) < Decimal("1e-40") and int(nearest) % 2 == 1:
            return -((-base) ** exponent)
        raise MathError("The power of a negative number is not real")

    return base ** exponent


def modulus(left, right):
    if right == 0:
        raise MathError("Division by zero is undefined")
    # Mathematical modulo: the real app gives -7 mod 3 = 2, matching Python's
    # sign-of-divisor result rather than C's truncated remainder.
    return left - right * (left / right).to_integral_value(rounding="ROUND_FLOOR")


def divide(left, right):
    if right == 0:
        raise MathError("Division by zero is undefined")
    return left / right


def factorial(value):
    if value != value.to_integral_value() or value < 0:
        raise MathError("Factorial is only defined for non-negative integers")
    result = Decimal(1)
    for i in range(2, int(value) + 1):
        result *= i
    return result
