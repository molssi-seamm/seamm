"""'${...}' inside a text parameter's value is expanded when the job runs
(Paul, 2026-11-06: braces only, on by default, with "expand": False to opt out)."""

import pytest

import seamm
from seamm import templates
from seamm.builder import FlowchartBuildError, check_expression, check_value

CONTEXT = {"file": "C8_111-65-9", "n": 7, "T": 298.15, "row": {"a": "x"}}


def parameter(value, kind="string", **extra):
    p = seamm.Parameter(
        {"default": "", "kind": kind, "default_units": None, "enumeration": tuple()}
        | extra
    )
    p.value = value
    return p


@pytest.mark.parametrize(
    "text, expected",
    [
        ("/data/${file}.sdf", "/data/C8_111-65-9.sdf"),
        ("${file}.sdf", "C8_111-65-9.sdf"),
        ("C${n:02d}.sdf", "C07.sdf"),
        ("${T + 10:.1f} K", "308.1 K"),
        ("${row['a']}-${row[\"a\"]}", "x-x"),
        ("${ {'k': n}['k'] }", "7"),
        ("cost $5 and $${literal}", "cost $5 and ${literal}"),
        ("no variables {here}", "no variables {here}"),
        ("${file!r}", "'C8_111-65-9'"),
    ],
)
def test_expand(text, expected):
    assert templates.expand(text, CONTEXT) == expected


def test_errors_name_the_field():
    with pytest.raises(templates.TemplateError, match="NameError"):
        templates.expand("/data/${nope}.sdf", CONTEXT)
    with pytest.raises(templates.TemplateError, match="not closed"):
        templates.expand("/data/${file.sdf", CONTEXT)
    with pytest.raises(templates.TemplateError, match="Empty"):
        templates.expand("/data/${}.sdf", CONTEXT)


def test_whole_expression():
    assert templates.whole_expression("${n}") == "n"
    assert templates.whole_expression("${n + 1}") == "n + 1"
    assert templates.whole_expression("${n:02d}") is None
    assert templates.whole_expression("${n}.sdf") is None
    assert templates.whole_expression("$n") is None


def test_text_parameter_expands_inline():
    assert (
        parameter("/data/${file}.sdf").get(context=CONTEXT) == "/data/C8_111-65-9.sdf"
    )


def test_whole_value_forms_are_unchanged_and_typed():
    assert parameter("$n", kind="integer").get(context=CONTEXT) == 7
    assert parameter("=n * 2", kind="integer").get(context=CONTEXT) == 14
    assert parameter("$file", kind="string").get(context=CONTEXT) == "C8_111-65-9"
    # Exactly one ${...} is the value itself, typed; it used to be a Python set
    assert parameter("${n}", kind="integer").get(context=CONTEXT) == 7
    assert parameter("${row}", kind="dictionary").get(context=CONTEXT) == {"a": "x"}


def test_opt_out_keeps_the_text():
    script = "variable T equal 300\nfix 1 all nvt temp ${T} ${T} 100"
    p = parameter(script, expand=False)
    assert not p.is_template
    assert p.get(context=CONTEXT) == script


def test_only_text_parameters_expand():
    p = parameter("${n}0", kind="integer")
    assert not p.is_expr and not p.is_template


def test_unknown_variable_names_the_parameter():
    parameters = seamm.Parameters(
        defaults={
            "file": {
                "default": "/data/${nope}.sdf",
                "kind": "string",
                "default_units": None,
                "enumeration": tuple(),
            }
        }
    )
    with pytest.raises(templates.TemplateError, match="'file' = '/data/"):
        parameters.current_values_to_dict(context=CONTEXT)


def test_builder_checks_the_syntax():
    check_expression("/data/${file}.sdf", "file")
    check_expression("${n}", "n")
    with pytest.raises(FlowchartBuildError, match="not valid Python"):
        check_expression("/data/${file +}.sdf", "file")
    with pytest.raises(FlowchartBuildError, match="not closed"):
        check_expression("/data/${file.sdf", "file")


def test_builder_refuses_inline_in_a_number():
    with pytest.raises(FlowchartBuildError, match="only for text parameters"):
        check_value(parameter("", kind="integer"), "${n}0", name="steps")
    value, units = check_value(parameter(""), "/data/${file}.sdf", name="file")
    assert value == "/data/${file}.sdf"


def test_variables_value():
    variables = seamm.Variables()
    old = seamm.flowchart_variables
    seamm.flowchart_variables = variables
    try:
        variables.set_variable("method", "B3LYP")
        variables.set_variable("n", 3)
        assert variables.value("E_${method}") == "E_B3LYP"
        assert variables.value("${n}") == 3
        assert variables.value("$n") == 3
        assert variables.value("plain") == "plain"
    finally:
        seamm.flowchart_variables = old


def test_safe_format_leaves_variables_for_the_job():
    from seamm.standard_parameters import safe_format

    text = "ALK:${file.split('_')[0]} {title}"
    assert safe_format(text, title="t") == "ALK:${file.split('_')[0]} t"
    assert safe_format("{unknown} {title}", title="t") == "{unknown} t"
    assert safe_format("{a.b}") == "{a.b}"
