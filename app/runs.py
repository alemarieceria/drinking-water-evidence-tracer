"""Atomic local run records; interrupted writes never replace an intact record."""

import os
import tempfile
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.models import RunRecord


class RunStorageError(Exception):
    """Run storage failed; messages must not contain filesystem paths or keys."""


def save_run(root: Path, record: RunRecord) -> None:
    temporary: Path | None = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=root,
            prefix=f".{record.run_id}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(record.model_dump_json(indent=2))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, root / f"{record.run_id}.json")
    except OSError:
        raise RunStorageError("The local run record could not be saved.") from None
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def load_run(root: Path, run_id: UUID) -> RunRecord:
    if not isinstance(run_id, UUID):
        raise RunStorageError("A valid run ID is required.")
    try:
        return RunRecord.model_validate_json((root / f"{run_id}.json").read_bytes())
    except OSError, ValidationError:
        raise RunStorageError(
            "The local run record is unavailable or invalid."
        ) from None
