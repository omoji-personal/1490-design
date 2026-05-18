# tests/test_build_sourcing_cli.py
"""R5 Min1 — build_sourcing.py uses argparse instead of an ad-hoc
`in sys.argv` string scan. These tests pin the parser behavior so a
future refactor can't silently regress the flag contract.
"""
import pytest

from build_sourcing import _parse_args


def test_parse_args_defaults():
    """No flags -> both booleans are False."""
    args = _parse_args([])
    assert args.allow_missing_suppliers is False
    assert args.trigger_t3 is False


def test_parse_args_allow_missing_suppliers():
    """`--allow-missing-suppliers` flips allow_missing_suppliers True."""
    args = _parse_args(["--allow-missing-suppliers"])
    assert args.allow_missing_suppliers is True
    assert args.trigger_t3 is False


def test_parse_args_trigger_t3():
    """`--trigger-t3` flips trigger_t3 True."""
    args = _parse_args(["--trigger-t3"])
    assert args.trigger_t3 is True
    assert args.allow_missing_suppliers is False


def test_parse_args_both_flags():
    """Both flags together compose."""
    args = _parse_args(["--allow-missing-suppliers", "--trigger-t3"])
    assert args.allow_missing_suppliers is True
    assert args.trigger_t3 is True


def test_parse_args_typo_fails_loud():
    """R5 Min1 — typos like `--trigger_t3` (underscore not dash) used to be
    silently ignored by the ad-hoc `in sys.argv` scan. argparse must reject."""
    with pytest.raises(SystemExit):
        _parse_args(["--trigger_t3"])


def test_parse_args_unknown_flag_fails_loud():
    """argparse rejects unknown flags with a clear error."""
    with pytest.raises(SystemExit):
        _parse_args(["--build-vendors-only"])
