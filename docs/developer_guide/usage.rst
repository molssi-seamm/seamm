=====
Usage
=====

To use the SEAMM module in a project::

    import seamm

Help text and tooltips
----------------------

Each parameter in a step's ``*_parameters.py`` has a short ``description``, which is the
label of its widget in the dialog, and a longer ``help_text``. ``Parameter.widget()``
shows the ``help_text`` as a tooltip: it pops up when the pointer rests on the label or
the field for a moment. Write it for the user of the dialog: what the setting does, its
units or valid values, and when it matters. Line breaks and indentation in the text do
not matter, since the tooltip reflows it; a blank line starts a new paragraph.

A dialog can override the text, or give a hand-built widget a tooltip, with the
``tooltip`` option of the ``seamm_widgets`` labeled widgets::

    self["basis"] = P["basis"].widget(frame, tooltip="Only used when ...")
    w = sw.LabeledEntry(frame, labeltext="Charge:", tooltip="The total charge.")
