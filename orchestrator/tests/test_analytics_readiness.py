import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import mock

import azure.functions as func

import analytics_events
import readiness
import readiness_skills
import readiness_service


class AnalyticsEventsTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"PULSE_ANALYTICS_ENABLED": "false"}, clear=False)
    def test_record_session_scorecard_event_noop_when_disabled(self) -> None:
        with mock.patch.object(analytics_events.analytics_db, "get_connection") as conn_mock:
            analytics_events.record_session_scorecard_event(
                "sess-1",
                {"user_id": "11111111-1111-1111-1111-111111111111"},
                {"overall": {"score": 0.9}},
            )

        conn_mock.assert_not_called()

    @mock.patch.dict(os.environ, {"PULSE_ANALYTICS_ENABLED": "true"}, clear=False)
    def test_record_session_scorecard_event_inserts_when_enabled(self) -> None:
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        @contextmanager
        def fake_get_connection():  # type: ignore[return-type]
            yield mock_conn

        with mock.patch.object(analytics_events.analytics_db, "get_connection", fake_get_connection):
            analytics_events.record_session_scorecard_event(
                "sess-1",
                {"user_id": "11111111-1111-1111-1111-111111111111", "persona": "Thinker"},
                {"overall": {"score": 0.9}},
            )

        mock_cursor.execute.assert_called_once()
        query, params = mock_cursor.execute.call_args.args
        assert "INSERT INTO analytics.session_events" in query
        self.assertEqual(params["session_id"], "sess-1")
        self.assertEqual(params["pulse_step"], "session_end")
        self.assertEqual(params["skill_tag"], "overall")


class ReadinessServiceTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"PULSE_READINESS_ENABLED": "false"}, clear=False)
    def test_compute_and_store_user_readiness_disabled_is_noop(self) -> None:
        with mock.patch.object(readiness_service.analytics_db, "get_connection") as conn_mock:
            result = readiness_service.compute_and_store_user_readiness("11111111-1111-1111-1111-111111111111")

        self.assertIsNone(result)
        conn_mock.assert_not_called()

    @mock.patch.dict(os.environ, {"PULSE_READINESS_ENABLED": "true"}, clear=False)
    def test_compute_and_store_user_readiness_with_aggregates_inserts_snapshot(self) -> None:
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # SELECT from analytics.session_events returns three aggregates
        mock_cursor.fetchall.return_value = [
            ("communication", 70.0, 4),
            ("technical_depth", 80.0, 3),
            ("overall", 75.0, 7),
        ]

        @contextmanager
        def fake_get_connection():  # type: ignore[return-type]
            yield mock_conn

        with mock.patch.object(readiness_service.analytics_db, "get_connection", fake_get_connection):
            snapshot = readiness_service.compute_and_store_user_readiness(
                "11111111-1111-1111-1111-111111111111",
            )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        # With the configured weights and aggregates, overall should be ~75
        self.assertEqual(snapshot["readiness_overall"], 75.0)

        # Ensure we attempted to insert into analytics.user_readiness
        queries = [call.args[0] for call in mock_cursor.execute.call_args_list]
        self.assertTrue(
            any("INSERT INTO analytics.user_readiness" in str(q) for q in queries),
            "expected INSERT into analytics.user_readiness",
        )

    @mock.patch.dict(os.environ, {"PULSE_READINESS_ENABLED": "true"}, clear=False)
    def test_compute_and_store_user_readiness_for_session_without_user_id_is_noop(self) -> None:
        with mock.patch.object(readiness_service, "compute_and_store_user_readiness") as inner_mock:
            result = readiness_service.compute_and_store_user_readiness_for_session({"session_id": "abc"})

        self.assertIsNone(result)
        inner_mock.assert_not_called()

    @mock.patch.dict(os.environ, {"PULSE_READINESS_ENABLED": "true"}, clear=False)
    def test_compute_and_store_user_readiness_for_session_with_user_id_delegates(self) -> None:
        with mock.patch.object(readiness_service, "compute_and_store_user_readiness", return_value={"ok": True}) as inner_mock:
            result = readiness_service.compute_and_store_user_readiness_for_session(
                {"session_id": "abc", "user_id": "11111111-1111-1111-1111-111111111111"},
            )

        self.assertEqual(result, {"ok": True})
        inner_mock.assert_called_once_with("11111111-1111-1111-1111-111111111111")


class ReadinessEndpointTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    def test_readiness_missing_user_id_returns_400(self) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/readiness",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
        resp = readiness.main(req)
        self.assertEqual(resp.status_code, 400)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    def test_readiness_returns_latest_and_history(self) -> None:
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        now = datetime(2025, 11, 28, 12, 0, 0, tzinfo=timezone.utc)
        earlier = datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc)
        mock_cursor.fetchall.return_value = [
            (now, 72.5, 75.0, 70.0, 68.0, 74.0),
            (earlier, 60.0, None, None, None, None),
        ]

        @contextmanager
        def fake_get_connection():  # type: ignore[return-type]
            yield mock_conn

        with mock.patch.object(readiness, "get_connection", fake_get_connection):
            req = func.HttpRequest(
                method="GET",
                url="/readiness/1111",
                headers={},
                params={},
                route_params={"userId": "11111111-1111-1111-1111-111111111111"},
                body=b"",
            )
            resp = readiness.main(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertEqual(data["userId"], "11111111-1111-1111-1111-111111111111")
        self.assertIsInstance(data.get("history"), list)
        self.assertGreaterEqual(len(data["history"]), 1)
        latest = data["latest"]
        self.assertEqual(latest["overall"], 72.5)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    def test_readiness_skills_missing_user_id_returns_400(self) -> None:
        req = func.HttpRequest(
            method="GET",
            url="/readiness/skills",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
        resp = readiness_skills.main(req)
        self.assertEqual(resp.status_code, 400)

    @mock.patch.dict(os.environ, {"TRAINING_ORCHESTRATOR_ENABLED": "true"}, clear=False)
    def test_readiness_skills_returns_skills(self) -> None:
        mock_conn = mock.MagicMock()
        mock_cursor = mock.MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            ("communication", "30d", 72.5, 8),
            ("technical_depth", "30d", 81.0, 5),
        ]

        @contextmanager
        def fake_get_connection():  # type: ignore[return-type]
            yield mock_conn

        with mock.patch.object(readiness_skills, "get_connection", fake_get_connection):
            req = func.HttpRequest(
                method="GET",
                url="/readiness/1111/skills",
                headers={},
                params={},
                route_params={"userId": "11111111-1111-1111-1111-111111111111"},
                body=b"",
            )
            resp = readiness_skills.main(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_body())
        self.assertEqual(data["userId"], "11111111-1111-1111-1111-111111111111")
        skills = data.get("skills")
        assert isinstance(skills, list)
        self.assertEqual(len(skills), 2)
        self.assertEqual(skills[0]["skillTag"], "communication")


if __name__ == "__main__":
    unittest.main()
