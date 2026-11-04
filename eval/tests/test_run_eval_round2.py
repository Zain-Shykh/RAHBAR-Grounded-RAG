"""Round 2 break attempts on the baseline read and the ask-loop catch."""
import sys

import httpx
import pytest
import run_eval


def _golden(tmp_path):
    g = tmp_path / "g.yaml"
    g.write_text('questions:\n- {id: q1, question: "hi", type: ordinary, relevant: [{source: a.pdf, section: "1"}]}\n')
    return g


def _run(monkeypatch, tmp_path, body, baseline_text=None):
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=body))
    real = httpx.Client
    monkeypatch.setattr(run_eval.httpx, "Client", lambda **kw: real(transport=transport, **kw))
    argv = ["run_eval.py", "--api", "http://x", "--golden", str(_golden(tmp_path)),
            "--out", str(tmp_path / "o.json"), "--baseline", str(tmp_path / "b.json")]
    if baseline_text is not None:
        (tmp_path / "b.json").write_text(baseline_text)
    monkeypatch.setattr(sys, "argv", argv)
    return run_eval.main()


@pytest.mark.parametrize("body", [b"[]", b'["a"]', b'"s"', b"5", b"null", b"true"])
def test_non_object_ask_body_aborts_cleanly(monkeypatch, tmp_path, body):
    assert _run(monkeypatch, tmp_path, body) == 1
    assert not (tmp_path / "o.json").exists()


@pytest.mark.parametrize("text", ["", "{bad", "\u0000"])
def test_unparseable_baseline_aborts_cleanly(monkeypatch, tmp_path, text):
    assert _run(monkeypatch, tmp_path, b'{"answer": "x", "citations": [], "retrieved": []}', text) == 1
    assert not (tmp_path / "o.json").exists()


@pytest.mark.parametrize("text", ["[]", "null"])
def test_empty_or_null_baseline_tolerated(monkeypatch, tmp_path, text):
    assert _run(monkeypatch, tmp_path, b'{"answer": "x", "citations": [], "retrieved": []}', text) in (0, 1)


@pytest.mark.parametrize("text", ["[1]", '"s"', "5", '{"recall_at_5": "x"}'])
def test_wrong_shape_baseline_does_not_traceback(monkeypatch, tmp_path, text):
    # D-2: valid JSON of the wrong shape currently raises AttributeError/TypeError in gate().
    assert _run(monkeypatch, tmp_path, b'{"answer": "x", "citations": [], "retrieved": []}', text) == 1


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_baseline_recall_aborts_cleanly(monkeypatch, tmp_path, value):
    body = b'{"answer": "x", "citations": [], "retrieved": []}'
    assert _run(monkeypatch, tmp_path, body, '{"recall_at_5": %s}' % value) == 1
    assert not (tmp_path / "o.json").exists()
