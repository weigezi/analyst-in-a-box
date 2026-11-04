"""A ratio whose denominator is a sum of identifiers displays as 0.00% in both periods. It must stop with a sentence."""

import pytest
import yaml

from aib import cli
from aib.run import run
from test_visits import BASE, CONV, CUR, answers, formed, shop  # noqa: F401  (shop is a fixture)


def test_a_denominator_that_sums_ids_stops_with_a_sentence(shop, capsys):
    ws_dir, _ = formed(shop, "bad", answers())
    model = yaml.safe_load((ws_dir / "model.yaml").read_text(encoding="utf-8"))
    model["measures"]["m_website_session_id"].update(agg="sum", column="website_session_id")
    model["measures"]["m_website_session_id"].pop("additive_over", None)
    (ws_dir / "model.yaml").write_text(yaml.safe_dump(model, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(Exception) as e:
        run(ws_dir, CONV, out_dir=shop["tmp"] / "run_bad")
    assert "sum of ids" in str(e.value) and "0.00%" not in str(e.value)
    assert not (shop["tmp"] / "run_bad" / "report.en.md").exists()
    code = cli.main(["run", "--workspace", str(ws_dir), "--metric", "conversion", "--current", *CUR, "--base", *BASE])
    err = capsys.readouterr().err
    assert code != 0 and "sum of ids" in err and "0.00%" not in err


def test_a_real_ratio_is_not_stopped(shop):
    ws_dir, _ = formed(shop, "ok_guard", answers())
    s = run(ws_dir, CONV, out_dir=shop["tmp"] / "run_ok_guard")
    assert not s["blocked"]
