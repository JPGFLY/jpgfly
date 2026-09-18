import unittest
from unittest.mock import patch

from app import DecisionRequest, SESSIONS, StartRequest, create_session, session_decision


class _FailingBrain:
    mode = "BROKEN TEST BRAIN"

    def decide(self, request, limits):
        raise RuntimeError("simulated art-brain failure")


class DumbDumbFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_support_nodes_offline_marks_candidate_brain_as_dumb_dumb(self):
        with patch("candidate_brain._support_nodes_online", return_value=False):
            created = await create_session(
                StartRequest(seed=54321, complexity=0.8, mutation=0.4, density=0.6)
            )
            session_id = created["session_id"]
            try:
                result = await session_decision(session_id, DecisionRequest(sequence=0))
                self.assertIn("DUMB DUMB MODE", result["brainMode"])
                self.assertIn("DUMB DUMB MODE", SESSIONS[session_id]["brain_mode"])
            finally:
                SESSIONS.pop(session_id, None)

    async def test_decision_failure_switches_to_pure_python_fallback(self):
        created = await create_session(
            StartRequest(seed=12345, complexity=0.8, mutation=0.4, density=0.6)
        )
        session_id = created["session_id"]
        try:
            session = SESSIONS[session_id]
            session["_brain"] = _FailingBrain()

            result = await session_decision(session_id, DecisionRequest(sequence=0))

            self.assertIn("DUMB DUMB MODE", result["brainMode"])
            self.assertEqual(
                SESSIONS[session_id]["brain_mode"],
                "DUMB DUMB MODE · PURE PYTHON FALLBACK",
            )
            self.assertEqual(result["sequence"], 0)
            self.assertIn(result["action"]["intent"], {"MOVE", "FINISH_ARTWORK"})
        finally:
            SESSIONS.pop(session_id, None)


if __name__ == "__main__":
    unittest.main()
