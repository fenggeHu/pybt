import json
import tempfile
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks

from ..models import RunStatus
from .store import store

ARTIFACTS_DIR = Path.cwd() / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def get_run_runner() -> Callable[[str], None]:
    """Return a callable that executes a run in the background."""

    def _run(run_id: str) -> None:
        run = store.get_run(run_id)
        if not run:
            return
        store.update_run(run_id, {"status": RunStatus.running, "progress": 0.1})
        try:
            from pybt import load_engine_from_json

            with tempfile.TemporaryDirectory() as td:
                cfg_path = Path(td) / "config.json"
                cfg_path.write_text(json.dumps(run.config, ensure_ascii=False), encoding="utf-8")
                engine = load_engine_from_json(cfg_path)
                engine.run()
                artifact_path = ARTIFACTS_DIR / f"{run_id}_config.json"
                artifact_path.write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
                store.update_run(
                    run_id,
                    {
                        "status": RunStatus.succeeded,
                        "progress": 1.0,
                        "artifacts": [str(artifact_path)],
                        "message": "completed",
                    },
                )
        except Exception as exc:
            store.update_run(run_id, {"status": RunStatus.failed, "message": str(exc), "progress": 1.0})

    return _run


def enqueue_run(run_id: str, tasks: BackgroundTasks) -> None:
    tasks.add_task(get_run_runner(), run_id)
