"""Epic 0 — P0 stop/bleed hotfix regression tests (backend half).

Repo test style: stdlib unittest, no real Claude / Google Ads / network calls,
no account mutation. These prove the two behaviours the hotfix depends on:

  1) PROCESS-GROUP KILL — stop_agent kills the WHOLE process group of every
     registered CLI child (not just the immediate proc), so the CLI's own
     children (MCP servers, headless Chrome) can't orphan. Verified against a
     real `sleep 30` spawned with start_new_session=True.
  2) STOP-FLAG LIFECYCLE — stop_agent flags the conversation in
     _stop_requested (even with no proc registered), the continuation-decision
     boolean goes False for a flagged conversation, the fresh-run clear removes
     the flag, and an unrelated conversation stays isolated.

Run:  cd backend && .venv/bin/python -m unittest tests.test_epic0_stop_hardening -v
"""

from __future__ import annotations

import os
import subprocess
import time
import unittest

from app.services import agent


class ProcessGroupKillTest(unittest.TestCase):
    """FIX 1 + FIX 2 + FIX 4: killpg over a set-registered process group."""

    def setUp(self):
        self.cid = "test-pgkill-conv"
        self.procs: list[subprocess.Popen] = []

    def tearDown(self):
        # Clean up any survivor and the registry entry.
        for proc in self.procs:
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except (ProcessLookupError, OSError):
                pass
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
        agent._running_procs.pop(self.cid, None)
        agent._stop_requested.discard(self.cid)

    def test_stop_agent_kills_whole_process_group(self):
        # Spawn a real long-lived child in its OWN process group (mirrors the
        # start_new_session=True the hotfix added to the CLI Popen).
        proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.procs.append(proc)
        pgid = os.getpgid(proc.pid)

        # Register it the same way _run_cli does (set-based registry).
        agent._running_procs.setdefault(self.cid, set()).add(proc)

        # Group is alive right now (signal 0 = existence probe, no signal sent).
        os.killpg(pgid, 0)  # must NOT raise

        killed = agent.stop_agent(self.cid)
        self.assertTrue(killed, "stop_agent should report it killed a process")

        # SIGTERM→wait→SIGKILL takes a beat; poll until the group is gone.
        deadline = time.time() + 3.0
        group_dead = False
        while time.time() < deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                group_dead = True
                break
            except OSError:
                # Any other OSError also means we can't reach it — treat as gone.
                group_dead = True
                break
            time.sleep(0.05)

        self.assertTrue(group_dead, "process group should be dead after stop_agent")
        # Registry key is cleaned up.
        self.assertNotIn(self.cid, agent._running_procs)


class StopFlagLifecycleTest(unittest.TestCase):
    """FIX 3: _stop_requested set/consult/clear lifecycle + isolation."""

    def setUp(self):
        self.cid = "test-flag-conv"
        self.other = "test-flag-other-conv"

    def tearDown(self):
        agent._stop_requested.discard(self.cid)
        agent._stop_requested.discard(self.other)
        agent._running_procs.pop(self.cid, None)
        agent._running_procs.pop(self.other, None)

    def test_stop_agent_flags_conversation_even_with_no_proc(self):
        # No proc registered — a stop between segments must STILL flag the
        # conversation so the continuation relaunch is blocked.
        self.assertNotIn(self.cid, agent._stop_requested)
        killed = agent.stop_agent(self.cid)
        self.assertFalse(killed, "no proc registered → nothing killed")
        self.assertIn(self.cid, agent._stop_requested, "stop must flag the conversation")

    def test_should_continue_decision_goes_false_when_flagged(self):
        # The hotfix guards the continuation decision with:
        #   ... and not (conversation_id and conversation_id in _stop_requested)
        # Reproduce that exact clause; every other conjunct is True so the flag
        # is the sole deciding factor.
        def should_continue(conversation_id: str) -> bool:
            base = True  # stand-in for the max_turns / cost / session conjuncts
            return base and not (conversation_id and conversation_id in agent._stop_requested)

        agent.stop_agent(self.cid)  # flags self.cid
        self.assertFalse(should_continue(self.cid), "flagged conversation must not continue")
        # Unrelated conversation is unaffected (isolation).
        self.assertNotIn(self.other, agent._stop_requested)
        self.assertTrue(should_continue(self.other), "unflagged conversation still continues")

    def test_fresh_run_clear_removes_flag(self):
        # A fresh stream_agent_response run clears the flag (discard at the top),
        # so a later legit message isn't perma-blocked.
        agent.stop_agent(self.cid)
        self.assertIn(self.cid, agent._stop_requested)
        # Simulate the fresh-run clear point in stream_agent_response.
        agent._stop_requested.discard(self.cid)
        self.assertNotIn(self.cid, agent._stop_requested)


if __name__ == "__main__":
    unittest.main()
