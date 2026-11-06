"""Run files survive restart and interrupted replacement without corrupting evidence."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.models import ExtractionRequest, RunRecord
from app.runs import RunStorageError, load_run, save_run


def record() -> RunRecord:
    return RunRecord(
        request=ExtractionRequest(doc_id="DOC-0001", results_page=1, definitions_page=2)
    )


def test_run_round_trip_and_interrupted_state(tmp_path: Path) -> None:
    item = record()
    save_run(tmp_path, item)
    loaded = load_run(Path(str(tmp_path)), item.run_id)
    assert loaded.model_dump() == item.model_dump()
    assert loaded.status == "running"
    assert loaded.rows == []


def test_distinct_concurrent_runs_do_not_overwrite(tmp_path: Path) -> None:
    records = [record() for _ in range(3)]
    with ThreadPoolExecutor() as pool:
        list(pool.map(lambda item: save_run(tmp_path, item), records))
    assert {load_run(tmp_path, item.run_id).run_id for item in records} == {
        item.run_id for item in records
    }
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_failed_atomic_replacement_preserves_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    item = record()
    save_run(tmp_path, item)
    item.status = "error"

    def fail_replace(*args):
        raise OSError("unwritable")

    monkeypatch.setattr("app.runs.os.replace", fail_replace)
    with pytest.raises(RunStorageError):
        save_run(tmp_path, item)
    assert load_run(tmp_path, item.run_id).status == "running"
    assert not list(tmp_path.glob("*.tmp"))


def test_loading_never_accepts_arbitrary_path(tmp_path: Path) -> None:
    with pytest.raises(RunStorageError):
        load_run(tmp_path, "../../.env")
