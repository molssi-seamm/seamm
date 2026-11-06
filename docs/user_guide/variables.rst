.. _variables-in-parameters:

***********************
Variables in parameters
***********************
Steps such as Loop, Table and Parameters set flowchart variables, and any later
step can use them in the values of its parameters. There are two ways.

The whole value
===============
A value that is a variable or an expression is replaced by its value, with its type:
a number stays a number, a list a list.

* ``$name`` uses the variable ``name``, e.g. ``$SMILES`` or ``$T``. Units go after it,
  ``$T K``, or in the units field.
* ``$expression`` and ``=expression`` are Python, evaluated with the variables by their
  bare names, e.g. ``=2 * n`` or ``$_system_db.system.name``.
* ``${expression}``, alone, is the same as ``$expression``.

Inside text
===========
In a text parameter, such as a file name or a system name, each ``${...}`` is replaced
by its value, and the rest of the text is kept::

    /data/structures/${name}.sdf
    CBH:${SMILES}
    C${n:02d}.sdf
    ${T + 10:.1f} K

What is inside the braces is a Python expression with the variables by their bare
names, and may end with a format, as in a Python f-string: ``${n:02d}`` writes 7 as
``07``. The result is always text. ``$${`` gives a literal ``${``.

Only text parameters work this way. For a number, yes/no or choice parameter, use the
whole-value forms above, e.g. ``=10 * n``. A few text parameters are passed to a
program exactly as written and are not expanded, such as a LAMMPS script, whose own
variables are written ``${name}``, and the Python script of the Custom step.

A name that is not a variable, or an expression that fails, stops the step with a
message naming the parameter, rather than leaving the ``${...}`` in the text.
