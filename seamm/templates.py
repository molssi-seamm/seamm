# -*- coding: utf-8 -*-

"""Variables inside text: ``${...}`` in a parameter's value.

A value such as ``/data/${name}.sdf`` or ``C${n:02d}.sdf`` has each ``${...}``
replaced, when the job runs, by the Python expression inside the braces, evaluated
with the flowchart's variables and formatted as in an f-string (an optional
``!r``/``!s``/``!a`` conversion and ``:format`` spec). ``$${`` gives a literal ``${``.

This complements the whole-value forms, which are unchanged: ``$name`` or
``$expression`` and ``=expression`` give the value itself, with its type. A value
that is exactly one ``${expression}``, with no conversion or format, does the same.

Only text parameters expand ``${...}`` inside a value, and a parameter can opt out
with ``"expand": False`` in its definition (e.g. a LAMMPS script, whose own
variables are written ``${name}``).
"""


class TemplateError(ValueError):
    """A ``${...}`` that is not closed, is empty or cannot be evaluated."""


def has_template(value):
    """Whether a value has a ``${...}`` to expand, or a ``$${`` to unescape."""
    return isinstance(value, str) and "${" in value


def is_inline(value):
    """Whether a value is text with '${...}' in it to expand, rather than a
    whole-value variable or expression ('$x', '=x', or exactly '${x}')."""
    if not has_template(value):
        return False
    if value[0] == "=" or (value[0] == "$" and not value.startswith("${")):
        return False
    return whole_expression(value) is None


def _field_end(text, start):
    """The index of the ``}`` closing the field whose expression starts at `start`,
    skipping brackets and quoted strings; None if it is not closed."""
    depth = 0
    quote = None
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if text.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif c in "'\"":
            quote = text[i : i + 3] if text[i : i + 3] in ("'''", '"""') else c
            i += len(quote)
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]":
            depth -= 1
        elif c == "}":
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return None


def parse(text):
    """Split text into literal pieces and ``${...}`` fields.

    Returns
    -------
    [(str, bool)]
        Each piece and whether it is a field (its inside, e.g. ``n:02d``) rather
        than literal text. ``$${`` comes back as the literal ``${``.

    Raises
    ------
    TemplateError
        For a ``${`` without its ``}``, or an empty ``${}``.
    """
    pieces = []
    literal = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("$${", i):
            literal.append("${")
            i += 3
        elif text.startswith("${", i):
            end = _field_end(text, i + 2)
            if end is None:
                raise TemplateError(f"The '${{' at position {i + 1} is not closed")
            inside = text[i + 2 : end]
            if inside.strip() == "":
                raise TemplateError(f"Empty '${{}}' at position {i + 1}")
            if literal:
                pieces.append(("".join(literal), False))
                literal = []
            pieces.append((inside, True))
            i = end + 1
        else:
            literal.append(text[i])
            i += 1
    if literal:
        pieces.append(("".join(literal), False))
    return pieces


def _split_field(inside):
    """The expression of a field, without any ``!conversion`` or ``:format``."""
    depth = 0
    quote = None
    i = 0
    while i < len(inside):
        c = inside[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if inside.startswith(quote, i):
                i += len(quote)
                quote = None
                continue
        elif c in "'\"":
            quote = inside[i : i + 3] if inside[i : i + 3] in ("'''", '"""') else c
            i += len(quote)
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c == ":":
            return inside[:i]
        elif depth == 0 and c == "!" and inside[i + 1 : i + 2] != "=":
            return inside[:i]
        i += 1
    return inside


def whole_expression(value):
    """The expression of a value that is exactly one ``${expression}``, with no
    conversion or format; else None."""
    if not (isinstance(value, str) and value.startswith("${")):
        return None
    try:
        pieces = parse(value)
    except TemplateError:
        return None
    if len(pieces) != 1 or not pieces[0][1]:
        return None
    inside = pieces[0][0]
    if _split_field(inside) != inside:
        return None
    return inside


def check(text):
    """Check the syntax of every ``${...}`` in text.

    Raises
    ------
    TemplateError
        For an unclosed or empty field, or one that is not valid Python.
    """
    for inside, is_field in parse(text):
        if is_field:
            try:
                compile(f'f"{{{inside}}}"', "<template>", "eval")
            except SyntaxError as e:
                raise TemplateError(f"'${{{inside}}}' is not valid Python: {e.msg}")


def expand(text, context):
    """Replace every ``${...}`` in text by its value in the context.

    Parameters
    ----------
    text : str
        The text, e.g. ``/data/${name}.sdf``.
    context : dict
        The variables, e.g. ``seamm.flowchart_variables._data``.

    Returns
    -------
    str

    Raises
    ------
    TemplateError
        For an unclosed or empty field, or one that cannot be evaluated, e.g. a
        variable that does not exist.
    """
    result = []
    for piece, is_field in parse(text):
        if not is_field:
            result.append(piece)
            continue
        try:
            # An f-string with one field gives f-string formatting; Python 3.12
            # allows any quotes inside the field (PEP 701)
            result.append(eval(f'f"{{{piece}}}"', context))  # noqa: S307
        except Exception as e:
            raise TemplateError(
                f"Could not evaluate '${{{piece}}}': {type(e).__name__}: {e}"
            ) from e
    return "".join(result)
