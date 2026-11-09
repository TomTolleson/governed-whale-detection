import json

from src.audit import GENESIS_HASH, _sha256, log_event, verify_chain


def test_first_entry_uses_genesis_hash(tmp_path):
    log = tmp_path / "log.jsonl"
    entry = log_event("tester", "start", {"x": 1}, log_path=log)
    assert entry["prev_hash"] == GENESIS_HASH
    assert entry["timestamp"].endswith("+00:00")  # UTC


def test_chain_links_each_line_to_previous(tmp_path):
    log = tmp_path / "log.jsonl"
    log_event("tester", "a", log_path=log)
    log_event("tester", "b", log_path=log)
    log_event("tester", "c", log_path=log)
    lines = log.read_text().splitlines()
    assert len(lines) == 3
    for prev, cur in zip(lines, lines[1:]):
        assert json.loads(cur)["prev_hash"] == _sha256(prev)
    assert verify_chain(log)


def test_append_only_keeps_earlier_lines(tmp_path):
    log = tmp_path / "log.jsonl"
    log_event("tester", "a", log_path=log)
    first = log.read_text()
    log_event("tester", "b", log_path=log)
    assert log.read_text().startswith(first)


def test_tampering_is_detected(tmp_path):
    log = tmp_path / "log.jsonl"
    log_event("tester", "a", {"v": 1}, log_path=log)
    log_event("tester", "b", log_path=log)
    lines = log.read_text().splitlines()
    lines[0] = lines[0].replace('"v": 1', '"v": 2')
    log.write_text("\n".join(lines) + "\n")
    assert not verify_chain(log)
