import json
import os
import unittest
from unittest import mock

import azure.functions as func

import trainer_pulse_step as trainer


def make_request(body: object | None, method: str = "POST") -> func.HttpRequest:
    """Helper to build an HttpRequest for trainer_pulse_step."""
    raw = json.dumps(body).encode("utf-8") if body is not None else b""
    return func.HttpRequest(
        method=method,
        url="/trainer/pulse/step",
        headers={},
        params={},
        route_params={},
        body=raw,
    )


class TrainerPulseStepTests(unittest.TestCase):
    def test_options_returns_no_content_with_cors(self) -> None:
        req = func.HttpRequest(
            method="OPTIONS",
            url="/trainer/pulse/step",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
        resp = trainer.main(req)

        self.assertEqual(resp.status_code, 204)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_method_not_allowed(self) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/trainer/pulse/step",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
        resp = trainer.main(req)

        self.assertEqual(resp.status_code, 405)
        self.assertIn(b"Method not allowed", resp.get_body())
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    def test_invalid_json_returns_400(self) -> None:
        req = func.HttpRequest(
            method="POST",
            url="/trainer/pulse/step",
            headers={},
            params={},
            route_params={},
            body=b"not-json",
        )
        resp = trainer.main(req)

        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"Invalid JSON", resp.get_body())

    @mock.patch.dict(os.environ, {"PULSE_TRAINER_ENABLED": "false"}, clear=False)
    def test_trainer_disabled_by_env_returns_static_evaluation(self) -> None:
        body = {"config": {}, "session": {"pulse_step": "Probe"}}
        req = make_request(body)

        resp = trainer.main(req)
        data = json.loads(resp.get_body())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["mode"], "static_evaluation")
        self.assertIn("disabled in this environment", data["diagnosis"]["brief_explanation"])

    @mock.patch.dict(os.environ, {"PULSE_TRAINER_ENABLED": "true"}, clear=False)
    def test_adaptive_trainer_disabled_in_config_returns_static_evaluation(self) -> None:
        body = {
            "config": {"adaptive_trainer": {"enabled": False, "self_annealing_enabled": False}},
            "session": {"pulse_step": "Probe"},
        }
        req = make_request(body)

        resp = trainer.main(req)
        data = json.loads(resp.get_body())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["mode"], "static_evaluation")
        self.assertIn("adaptive trainer is disabled", data["diagnosis"]["brief_explanation"])

    @mock.patch.dict(os.environ, {"PULSE_TRAINER_ENABLED": "true"}, clear=False)
    @mock.patch.object(trainer, "_call_openai_trainer", side_effect=RuntimeError("boom"))
    def test_llm_failure_falls_back_to_stub_output(self, _: mock.Mock) -> None:
        body = {
            "config": {"adaptive_trainer": {"enabled": True, "self_annealing_enabled": False}},
            "session": {"pulse_step": "Probe", "latest_answer": {"learner_answer": "test"}},
        }
        req = make_request(body)

        resp = trainer.main(req)
        data = json.loads(resp.get_body())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data["mode"], "ask_followup")
        self.assertEqual(data["diagnosis"]["primary_error_type"], "missing_depth")
        self.assertTrue(data["next_question"]["text"])


class TrainerChangeLogTests(unittest.TestCase):
    def test_maybe_log_trainer_change_no_emit_does_nothing(self) -> None:
        config: dict[str, object] = {}
        session: dict[str, object] = {"pulse_step": "Probe"}
        output: dict[str, object] = {"trainer_change_log": {"emit": False}}

        with mock.patch.object(trainer, "write_json") as write_mock:
            trainer._maybe_log_trainer_change(config, session, output)

        write_mock.assert_not_called()

    def test_maybe_log_trainer_change_emit_true_writes_blob(self) -> None:
        config: dict[str, object] = {"adaptive_trainer": {"enabled": True, "self_annealing_enabled": True}}
        session: dict[str, object] = {
            "pulse_step": "Probe",
            "scenario": {"id": "scenario-1"},
            "learner_id": "learner-123",
            "session_id": "session-456",
        }
        output: dict[str, object] = {
            "trainer_change_log": {
                "emit": True,
                "observed_pattern": "pattern",
                "suspected_root_cause": "root",
                "proposed_rubric_changes": [],
                "proposed_prompt_changes": [],
                "proposed_scenario_changes": [],
                "examples_and_tips_for_trainers": [],
            }
        }

        with mock.patch.object(trainer, "write_json") as write_mock, mock.patch.object(
            trainer, "now_iso", return_value="2025-11-27T12:00:00Z"
        ):
            trainer._maybe_log_trainer_change(config, session, output)

        write_mock.assert_called_once()
        path_arg, payload_arg = write_mock.call_args.args
        assert isinstance(path_arg, str)
        assert path_arg.startswith("trainer-change-logs/2025-11-27/Probe/scenario-1/")
        assert payload_arg["trainer_change_log"]["emit"] is True


if __name__ == "__main__":
    unittest.main()
