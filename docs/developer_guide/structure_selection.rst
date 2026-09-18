===================================
Selecting structures in a plug-in
===================================

Many steps operate on existing structures: writing them to a file, extracting
clusters from them, looping over them. Rather than each plug-in inventing its
own way of saying *which* structures, SEAMM provides a standard parameter block
and a single implementation of the selection.

The parameters
--------------

Include ``seamm.standard_parameters.structure_selection_parameters`` in the
step's parameters::

    parameters = {
        **seamm.standard_parameters.structure_selection_parameters,
        "my option": {...},
    }

It contributes four parameters:

``source systems``
    ``current`` (the default), ``all``, or ``name is`` / ``name matches`` /
    ``name regexp`` together with ``source system name``. A variable, e.g.
    ``$frames``, holding a list of configurations or of systems may also be
    given.
``source system name``
    The name, shell-wildcard pattern or regular expression for the systems.
``source configurations``
    Which configurations of each selected system: ``current`` (the default),
    ``all``, ``last``, ``first``, or ``name is`` / ``name matches`` /
    ``name regexp`` together with ``source configuration name``.
``source configuration name``
    The name, pattern or regular expression for the configurations.

The defaults select exactly the current configuration of the current system, so
adding the block to an existing step does not change its behaviour until the
user asks for more.

Using the selection
-------------------

In ``run()``, after dereferencing the parameters::

    P = self.parameters.current_values_to_dict(context=seamm.flowchart_variables._data)
    configurations = self.select_configurations(P)
    for configuration in configurations:
        ...

``Node.select_configurations`` returns the configurations in system order and
then configuration order, and raises a ``ValueError`` naming the selection if
nothing matched (pass ``errors=False`` to get an empty list instead). The
underlying function, ``seamm.standard_parameters.select_configurations(system_db,
P)``, can be used and tested without a node.

For the step's description, ``structure_selection_description(P)`` returns a
sentence such as *"All configurations of the systems matching 'H2O*' will be
used."*

The dialog
----------

In the Tk node, create the widgets in ``create_dialog`` and grid them in
``reset_dialog``::

    def create_dialog(self):
        frame = super().create_dialog(title="My Step")
        self.create_structure_selection_widgets(frame)
        ...

    def reset_dialog(self, widget=None):
        ...
        row, widgets = self.layout_structure_selection(row=row)
        sw.align_labels(widgets, sticky=tk.E)

``create_structure_selection_widgets`` binds the two choice comboboxes to
``reset_dialog``; ``layout_structure_selection`` grids the choices and shows a
name field beside a choice only when that choice needs one, so the user cannot
build a selection that is missing its name.

Semantics shared with existing steps
------------------------------------

The vocabulary is the Loop step's (``name is`` / ``name matches`` /
``name regexp``, ``all`` / ``last`` / ``first``) and the ``current`` choices of
Write Structure, so flowcharts read consistently across steps. Those steps, and
the Dimer Builder's private equivalent, are being converted to this block.
