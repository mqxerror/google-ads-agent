"""Draft jobs as DB rows — restart survival + fence F6 grep-audit (story 15.3).

Two guarantees:

1. **Restart harness (FR4.3, NFR-R1):** a completed job's result is retrievable
   after an app-context recreation; an in-flight (`running`) job reads back
   `interrupted` — with its full `request_json` intact — after the boot sweep,
   so the wizard can offer a one-click re-run (never a 404).

2. **Fence F6 (grep-audit):** no module-level dict literal remains on any draft
   path (`demand_gen.py`, `pmax.py`, `creative_copy.py`) — job state lives ONLY
   as DB rows. This runs in the DEFAULT collection so no later story can merge a
   resurrected in-memory job store.

Run:  cd backend && .venv/bin/python -m unittest tests.test_creative_jobs_restart -v
"""

from __future__ import annotations

import ast
import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="creative-jobs-restart-test-"))
settings.DATA_DIR = _TMP

from app.database import (  # noqa: E402
    get_db,
    init_db,
    sweep_interrupted_creative_jobs,
)
from app.services import creative_copy  # noqa: E402

_BACKEND = Path(__file__).resolve().parents[1]

# The draft-path files fence F6 watches. A module-level dict literal here is the
# in-memory job-store failure class the story deletes.
_DRAFT_PATH_FILES = [
    _BACKEND / "app" / "routers" / "demand_gen.py",
    _BACKEND / "app" / "routers" / "pmax.py",
    _BACKEND / "app" / "services" / "creative_copy.py",
]


def setUpModule():
    _TMP.mkdir(parents=True, exist_ok=True)
    asyncio.run(init_db())


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _run(coro):
    return asyncio.run(coro)


class RestartHarness(unittest.TestCase):
    def test_completed_job_result_survives(self):
        async def _flow():
            job_id = await creative_copy.create_job(
                "draft", "acc-R", "pmax", {"brief": "panama"})
            await creative_copy.complete_job(job_id, {"headlines": ["Move to Panama"]})
            # Simulate a restart: a brand-new get_db connection re-reads the row.
            return await creative_copy.get_job(job_id)

        job = _run(_flow())
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["headlines"], ["Move to Panama"])

    def test_inflight_job_reads_interrupted_with_request(self):
        async def _flow():
            job_id = await creative_copy.create_job(
                "draft", "acc-R", "demand_gen", {"brief": "greece", "final_url": "x"})
            # It is `running` (the process died mid-draft). The boot sweep runs:
            swept = await sweep_interrupted_creative_jobs()
            job = await creative_copy.get_job(job_id)
            return swept, job

        swept, job = _run(_flow())
        self.assertGreaterEqual(swept, 1)
        self.assertEqual(job["status"], "interrupted")
        # the full request survives for one-click re-run
        self.assertEqual(job["request"]["brief"], "greece")
        self.assertIn("message", job)

    def test_unknown_job_is_none(self):
        self.assertIsNone(_run(creative_copy.get_job("does-not-exist")))

    def test_failed_job_carries_message(self):
        async def _flow():
            job_id = await creative_copy.create_job("draft", "acc-R", "pmax", None)
            await creative_copy.fail_job(job_id, "Creative Director returned no JSON")
            return await creative_copy.get_job(job_id)

        job = _run(_flow())
        self.assertEqual(job["status"], "error")
        self.assertIn("no JSON", job["message"])


class FenceF6NoModuleLevelJobDict(unittest.TestCase):
    """Grep-audit: no module-level dict literal on any draft path (job state has
    no memory home)."""

    def test_no_module_level_dict_on_draft_paths(self):
        offenders: list[str] = []
        for path in _DRAFT_PATH_FILES:
            self.assertTrue(path.exists(), f"draft-path file missing: {path}")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # MODULE level only
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                    value = node.value
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                    value = node.value
                else:
                    continue
                if isinstance(value, ast.Dict):
                    names = ", ".join(
                        t.id for t in targets if isinstance(t, ast.Name)) or "?"
                    offenders.append(f"{path.name}: module-level dict `{names}` "
                                     f"(line {node.lineno}) — job state must be DB rows")
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_retired_dicts_are_gone(self):
        for path, name in (
            (_BACKEND / "app" / "routers" / "demand_gen.py", "_dg_draft_jobs"),
            (_BACKEND / "app" / "routers" / "pmax.py", "_draft_jobs"),
        ):
            src = path.read_text(encoding="utf-8")
            self.assertNotIn(name, src, f"{name} resurrected in {path.name}")


if __name__ == "__main__":
    unittest.main()
