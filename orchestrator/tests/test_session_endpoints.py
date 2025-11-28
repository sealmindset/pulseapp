import json
import os
import unittest
from unittest import mock

import azure.functions as func

import session_start
import session_complete
import audio_chunk
import feedback_session


def make_json_request(url: str, body: object | None, method: str = "POST") -> func.HttpRequest:
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    return func.HttpRequest(
        method=method,
        url=url,
        headers={"Content-Type": "application/json"},
        params={},
        route_params={},
        body=raw,
    )


class SessionStartTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(session_start, "write_json")
    def test_session_start_returns_session_id(self, write_mock: mock.Mock) -> None:
        body = {"persona": "Thinker"}
        req = make_json_request("/session/start", body)

        resp = session_start.main(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertIn("sessionId", data)
        self.assertTrue(data["sessionId"])
        self.assertIn("avatarUrl", data)
        write_mock.assert_called_once()

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(session_start, "write_json")
    def test_session_start_persists_user_id_when_provided(self, write_mock: mock.Mock) -> None:
        body = {"persona": "Thinker", "userId": "11111111-1111-1111-1111-111111111111"}
        req = make_json_request("/session/start", body)

        resp = session_start.main(req)

        self.assertEqual(resp.status_code, 200)
        write_mock.assert_called_once()
        _path, doc = write_mock.call_args.args
        assert isinstance(doc, dict)
        self.assertEqual(doc.get("user_id"), "11111111-1111-1111-1111-111111111111")

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "false"}, clear=False)
    def test_session_start_disabled_returns_503(self) -> None:
        body = {"persona": "Thinker"}
        req = make_json_request("/session/start", body)

        resp = session_start.main(req)
        self.assertEqual(resp.status_code, 503)


class SessionCompleteTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(session_complete, "write_json")
    @mock.patch.object(session_complete, "read_json", return_value={"session_id": "abc"})
    def test_session_complete_marks_completed(
        self,
        _read_mock: mock.Mock,
        write_mock: mock.Mock,
    ) -> None:
        body = {"sessionId": "abc"}
        req = make_json_request("/session/complete", body)

        resp = session_complete.main(req)
        self.assertEqual(resp.status_code, 204)
        write_mock.assert_called_once()

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "false"}, clear=False)
    def test_session_complete_disabled_returns_503(self) -> None:
        body = {"sessionId": "abc"}
        req = make_json_request("/session/complete", body)

        resp = session_complete.main(req)
        self.assertEqual(resp.status_code, 503)


class AudioChunkTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    def test_audio_chunk_missing_session_id_returns_400(self) -> None:
        req = func.HttpRequest(
            method="POST",
            url="/audio/chunk",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
        resp = audio_chunk.main(req)
        self.assertEqual(resp.status_code, 400)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "false"}, clear=False)
    def test_audio_chunk_disabled_returns_503(self) -> None:
        req = func.HttpRequest(
            method="POST",
            url="/audio/chunk?sessionId=abc",
            headers={},
            params={"sessionId": "abc"},
            route_params={},
            body=b"",
        )
        resp = audio_chunk.main(req)
        self.assertEqual(resp.status_code, 503)


class FeedbackSessionTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(
        feedback_session,
        "read_json",
        side_effect=[{"persona": "Thinker", "status": "completed"}, None, None],
    )
    def test_feedback_session_returns_artifacts_with_empty_transcript(self, _read_mock: mock.Mock) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/feedback/abc",
            headers={},
            params={},
            route_params={"sessionId": "abc"},
            body=b"",
        )

        resp = feedback_session.main(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertIn("artifacts", data)
        self.assertIn("session", data)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(
        feedback_session,
        "read_json",
        side_effect=[
            {"persona": "Thinker", "status": "completed"},
            {"transcript": ["line1"]},
            {
                "overall": {"score": 0.9},
                "bce": {"score": 0.8, "passed": True, "summary": "BCE ok"},
                "mcf": {"score": 0.7, "passed": False, "summary": "MCF needs work"},
                "cpo": {"score": 0.6, "passed": True, "summary": "CPO ok"},
            },
        ],
    )
    def test_feedback_session_includes_scorecard_and_rubric(self, _read_mock: mock.Mock) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/feedback/abc",
            headers={},
            params={},
            route_params={"sessionId": "abc"},
            body=b"",
        )

        resp = feedback_session.main(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertEqual(data.get("overallScore"), 0.9)
        rubric = data.get("rubric")
        assert isinstance(rubric, list)
        self.assertEqual(len(rubric), 3)
        self.assertIn("scorecard", data)

    @mock.patch.dict(
        os.environ,
        {"TRAINING_ORCHESTRATOR_ENABLED": "true", "PULSE_EVALUATOR_ENABLED": "true"},
        clear=False,
    )
    @mock.patch.object(feedback_session, "_call_openai_pulse_evaluator", return_value={"framework": "PULSE"})
    @mock.patch.object(feedback_session, "_load_evaluator_prompt", return_value="SYSTEM PROMPT")
    @mock.patch.object(
        feedback_session,
        "read_json",
        side_effect=[{"persona": "Thinker", "status": "completed"}, {"transcript": ["line1"]}, None],
    )
    def test_feedback_session_includes_pulse_evaluator_when_enabled(
        self,
        _read_mock: mock.Mock,
        _prompt_mock: mock.Mock,
        _eval_mock: mock.Mock,
    ) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/feedback/abc",
            headers={},
            params={},
            route_params={"sessionId": "abc"},
            body=b"",
        )

        resp = feedback_session.main(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertIn("pulseEvaluator", data)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    @mock.patch.object(feedback_session, "read_json", return_value=None)
    def test_feedback_session_unknown_session_returns_404(self, _read_mock: mock.Mock) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/feedback/abc",
            headers={},
            params={},
            route_params={"sessionId": "abc"},
            body=b"",
        )

        resp = feedback_session.main(req)
        self.assertEqual(resp.status_code, 404)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "false"}, clear=False)
    def test_feedback_session_disabled_returns_503(self) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/feedback/abc",
            headers={},
            params={},
            route_params={"sessionId": "abc"},
            body=b"",
        )

        resp = feedback_session.main(req)
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
