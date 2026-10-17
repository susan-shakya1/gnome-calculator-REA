"""Tokenizer, parser and evaluator for the calculator's expression language."""

from decimal import Decimal

from . import number
from .number import MathError

# Keyboard equivalents normalise onto the glyphs the buttons insert.
ALIASES = {
    "-": "−",
    "*": "×",
    "/": "÷",
    "–": "−",
    "—": "−",
}

ADD, SUB = "+", "−"
MUL, DIV = "×", "÷"
ROOT = "√"
PI = "π"
EULER = "e"

OPERATORS = {ADD, SUB, MUL, DIV, ROOT, "^", "%", "!", "(", ")", "|"}

# `2²` is 4 and `2³` is 8: a run of superscript digits is a postfix exponent.
SUPERSCRIPT_DIGITS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}
SUPERSCRIPT_MINUS = "⁻"


class Token:
    __slots__ = ("kind", "text")

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text

    def __repr__(self):
        return f"Token({self.kind}, {self.text!r})"


class Node:
    __slots__ = ()


class Literal(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Binary(Node):
    __slots__ = ("op", "left", "right")

    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class Unary(Node):
    __slots__ = ("op", "operand")

    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class Percent(Node):
    """`x%` — meaning depends on the surrounding operator."""

    __slots__ = ("operand",)

    def __init__(self, operand):
        self.operand = operand


def _is_digit(char):
    return "0" <= char <= "9"


def tokenize(text):
    tokens = []
    i = 0
    length = len(text)
    while i < length:
        char = text[i]

        if char.isspace():
            i += 1
            continue

        char = ALIASES.get(char, char)

        # Must be ASCII-only: str.isdigit() is also true for superscripts,
        # which belong to the exponent branch below.
        if _is_digit(char) or char == ".":
            start = i
            seen_point = False
            while i < length and (_is_digit(text[i]) or (text[i] == "." and not seen_point)):
                if text[i] == ".":
                    seen_point = True
                i += 1
            tokens.append(Token("number", text[start:i]))
            continue

        if text.startswith("mod", i):
            tokens.append(Token("op", "mod"))
            i += 3
            continue

        if char in SUPERSCRIPT_DIGITS or char == SUPERSCRIPT_MINUS:
            digits = ""
            while i < length:
                current = text[i]
                if current in SUPERSCRIPT_DIGITS:
                    digits += SUPERSCRIPT_DIGITS[current]
                elif current == SUPERSCRIPT_MINUS and not digits:
                    digits += "-"
                else:
                    break
                i += 1
            tokens.append(Token("sup", digits))
            continue

        if char in (PI, EULER):
            tokens.append(Token("const", char))
            i += 1
            continue

        if char in OPERATORS:
            tokens.append(Token("op", char))
            i += 1
            continue

        raise MathError(f"Error: {text[i:]}")

    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self):
        token = self.peek()
        if token is not None:
            self.pos += 1
        return token

    def accept(self, text):
        token = self.peek()
        if token is not None and token.text == text:
            self.pos += 1
            return True
        return False

    def parse(self):
        if not self.tokens:
            raise MathError("")
        node = self.expression()
        if self.pos < len(self.tokens):
            raise MathError("Malformed expression")
        return node

    def expression(self):
        node = self.term()
        while True:
            token = self.peek()
            if token is None or token.text not in (ADD, SUB):
                return node
            self.take()
            node = Binary(token.text, node, self.term())

    def term(self):
        node = self.power()
        while True:
            token = self.peek()
            if token is None or token.text not in (MUL, DIV, "mod"):
                return node
            self.take()
            node = Binary(token.text, node, self.power())

    def power(self):
        base = self.unary()
        if self.accept("^"):
            # Right-associative: 2^3^2 is 2^(3^2).
            return Binary("^", base, self.power())
        return base

    def unary(self):
        token = self.peek()
        if token is not None and token.text == SUB:
            self.take()
            return Unary("neg", self.unary())
        if token is not None and token.text == ADD:
            self.take()
            return self.unary()
        if token is not None and token.text == ROOT:
            self.take()
            return Unary("sqrt", self.unary())
        return self.postfix()

    def postfix(self):
        node = self.primary()
        while True:
            token = self.peek()
            if token is None:
                return node
            if token.kind == "sup":
                self.take()
                node = Binary("^", node, Literal(Decimal(token.text)))
            elif token.text == "!":
                self.take()
                node = Unary("fact", node)
            elif token.text == "%":
                self.take()
                node = Percent(node)
            else:
                return node

    def primary(self):
        token = self.take()
        if token is None:
            raise MathError("Malformed expression")

        if token.kind == "number":
            return Literal(number.parse_number(token.text))

        if token.kind == "const":
            return Literal(number.PI if token.text == PI else number.E)

        if token.text == "(":
            node = self.expression()
            if not self.accept(")"):
                raise MathError("Missing closing parenthesis")
            return node

        if token.text == "|":
            node = self.expression()
            if not self.accept("|"):
                raise MathError("Missing closing |")
            return Unary("abs", node)

        raise MathError("Malformed expression")


def evaluate(node):
    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Percent):
        # Bare percentage, or percentage against × / ÷: just a hundredth.
        return evaluate(node.operand) / 100

    if isinstance(node, Unary):
        value = evaluate(node.operand)
        if node.op == "neg":
            return -value
        if node.op == "sqrt":
            return number.sqrt(value)
        if node.op == "abs":
            return abs(value)
        if node.op == "fact":
            return number.factorial(value)
        raise MathError("Malformed expression")

    if isinstance(node, Binary):
        left = evaluate(node.left)

        # `200+10%` is 220: against + and −, a percentage is taken *of the
        # left operand*. Against × and ÷ it stays a plain hundredth.
        if isinstance(node.right, Percent) and node.op in (ADD, SUB):
            share = left * evaluate(node.right.operand) / 100
            return left + share if node.op == ADD else left - share

        right = evaluate(node.right)
        if node.op == ADD:
            return left + right
        if node.op == SUB:
            return left - right
        if node.op == MUL:
            return left * right
        if node.op == DIV:
            return number.divide(left, right)
        if node.op == "mod":
            return number.modulus(left, right)
        if node.op == "^":
            return number.power(left, right)

    raise MathError("Malformed expression")


def solve(text):
    """Evaluate an equation string, returning the formatted result."""
    node = Parser(tokenize(text)).parse()
    return number.serialize(+evaluate(node))
