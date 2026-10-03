# -*- coding: utf-8 -*-

"""What happens between the steps of a running flowchart.

The flowchart evaluator and the Loop step (which runs its body itself) both call
:func:`step_completed` after each step, so that there is one place for it.
Today it commits the job database; flowchart checkpointing will add to it.
"""

import seamm


def step_completed(node=None):
    """Record that a step has finished: commit the job database.

    Parameters
    ----------
    node : seamm.Node
        The step that finished (unused for now).
    """
    variables = seamm.flowchart_variables
    if variables is not None and variables.exists("_system_db"):
        variables.get_variable("_system_db").db.commit()
