# -*- coding: utf-8 -*-

"""The job directory of a step's sub-flowchart (the evaluator of a parallel loop
iteration keeps its own files apart from the steps' directories)."""

from pathlib import Path

import seamm


def _step_with_subflowchart(flowchart):
    node = seamm.Node(flowchart=flowchart, title="Outer")
    flowchart.add_node(node)
    node.subflowchart = seamm.Flowchart(parent=node, name="Outer")
    node.subflowchart.root_directory = flowchart.root_directory
    return node


def test_a_job_directory_defaults_to_the_root_directory(tmp_path):
    flowchart = seamm.Flowchart(directory=str(tmp_path))
    node = _step_with_subflowchart(flowchart)
    assert flowchart.job_directory == str(tmp_path)
    assert node.subflowchart.job_directory == str(tmp_path)


def test_subflowcharts_have_the_job_directory_of_their_step(tmp_path):
    """As in an iteration's evaluator: the steps' directories are in the parent
    job's tree, the job's own files in _evaluator."""
    job = tmp_path / "job"
    evaluator = job / "4" / "iter_1" / "_evaluator"
    flowchart = seamm.Flowchart(directory=str(job))
    flowchart.job_directory = str(evaluator)
    outer = _step_with_subflowchart(flowchart)
    inner = _step_with_subflowchart(outer.subflowchart)
    assert outer.subflowchart.root_directory == str(job)
    assert outer.subflowchart.job_directory == str(evaluator)
    assert inner.subflowchart.job_directory == str(evaluator)

    # A sub-step's citations go to the evaluator's references.db
    evaluator.mkdir(parents=True)
    step = seamm.Node(flowchart=inner.subflowchart, title="Sub-step")
    references = step.references
    try:
        assert Path(references.conn.execute("PRAGMA database_list").fetchone()[2]) == (
            evaluator / "references.db"
        )
        assert not (job / "references.db").exists()
    finally:
        references.conn.close()


def test_a_subflowchart_can_be_given_its_own_job_directory(tmp_path):
    flowchart = seamm.Flowchart(directory=str(tmp_path))
    node = _step_with_subflowchart(flowchart)
    node.subflowchart.job_directory = str(tmp_path / "elsewhere")
    assert node.subflowchart.job_directory == str(tmp_path / "elsewhere")
