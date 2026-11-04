"""Expected failures (a wrong path, a broken answers file, an unreadable table) end in one plain sentence and exit 2.
An unexpected failure also stays short, and only --debug shows the traceback."""

import pytest

from aib import cli


def run_cli(capsys, *argv):
    rc = cli.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.err


def test_a_wrong_data_path_is_one_sentence_not_a_traceback(tmp_path, capsys):
    rc, err = run_cli(capsys, "init", str(tmp_path / "nope" / "orders.csv"), "--workspace", str(tmp_path / "ws"))
    assert rc == 2
    assert "Traceback" not in err and err.count("\n") <= 2
    assert "orders.csv" in err and "path" in err.lower()


def test_a_broken_input_file_is_named_and_says_what_to_fix(tmp_path, capsys):
    bad = tmp_path / "fix.yaml"
    bad.write_text("a: [unclosed\n  - b: : :\n", encoding="utf-8")
    rc, err = run_cli(capsys, "correct", "--workspace", str(tmp_path), "--json", str(bad))
    assert rc == 2 and "Traceback" not in err
    assert "fix.yaml" in err and "YAML or JSON" in err


def test_confirm_before_init_says_to_run_init(tmp_path, capsys):
    ok = tmp_path / "answers.yaml"
    ok.write_text("a: 1\n", encoding="utf-8")
    rc, err = run_cli(capsys, "confirm", "--workspace", str(tmp_path / "ws"), "--answers", str(ok))
    assert rc == 2 and "init" in err and "Traceback" not in err


def test_a_table_that_cannot_be_read_is_named(tmp_path, capsys):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    rc, err = run_cli(capsys, "init", str(empty), "--workspace", str(tmp_path / "ws"))
    assert rc == 2 and "Traceback" not in err and "empty.csv" in err


def test_an_unexpected_error_is_short_and_debug_shows_the_traceback(tmp_path, capsys, monkeypatch):
    def boom(args):
        raise RuntimeError("internal detail")
    monkeypatch.setattr(cli, "cmd_check", boom)
    rc, err = run_cli(capsys, "check", "--workspace", str(tmp_path))
    assert rc == 1 and "Traceback" not in err and "--debug" in err
    with pytest.raises(RuntimeError):
        cli.main(["--debug", "check", "--workspace", str(tmp_path)])
    with pytest.raises(RuntimeError):
        cli.main(["check", "--workspace", str(tmp_path), "--debug"])
