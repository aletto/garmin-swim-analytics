import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile

from test_fit import synthetic_fit

from swim_analytics.cli import _configured_key, main
from swim_analytics.connectors.personal import (
    MAX_DOWNLOAD,
    TOKEN_PATH,
    PersonalApiError,
    PersonalGarminSource,
)
from swim_analytics.storage import archived_activity_ids


class PersonalApiTests(unittest.TestCase):
    def test_downloads_original_fit_by_id(self):
        payload = synthetic_fit()
        output = io.BytesIO()
        with ZipFile(output, "w") as archive:
            archive.writestr("invented.fit", payload)

        with patch(
            "swim_analytics.connectors.personal._request",
            side_effect=[b'{"access_token":"test-token"}', output.getvalue()],
        ) as request:
            activities = list(PersonalGarminSource("test-key", (42,)).activities())

        self.assertEqual(activities[0].payload, payload)
        self.assertEqual(activities[0].external_id, "42")
        request.assert_any_call(TOKEN_PATH, "ApiKey test-key", "POST", 65536)
        request.assert_called_with(
            "/download-service/files/activity/42", "Bearer test-token", "GET", MAX_DOWNLOAD
        )

    def test_accepts_plain_and_json_string_token_responses(self):
        payload = synthetic_fit()
        for response in (b"fake.header.signature\n", b'"fake.header.signature"'):
            with (
                self.subTest(response=response),
                patch(
                    "swim_analytics.connectors.personal._request",
                    side_effect=[response, payload],
                ) as request,
            ):
                self.assertEqual(list(PersonalGarminSource("test-key", (42,)).activities())[0].payload, payload)
                request.assert_called_with(
                    "/download-service/files/activity/42",
                    "Bearer fake.header.signature", "GET", MAX_DOWNLOAD,
                )

    def test_rejects_html_without_printing_body(self):
        with patch(
            "swim_analytics.connectors.personal._request",
            return_value=b"<html>private response</html>",
        ) as request:
            with self.assertRaisesRegex(PersonalApiError, "unexpected token format") as error:
                list(PersonalGarminSource("test-key", (42,)).activities())
        self.assertNotIn("private response", str(error.exception))
        request.assert_called_once()

    def test_rejects_response_without_token(self):
        with patch("swim_analytics.connectors.personal._request", return_value=b"{}"):
            with self.assertRaisesRegex(PersonalApiError, "did not contain"):
                list(PersonalGarminSource("test-key", (42,)).activities())

    def test_rejects_download_without_fit(self):
        with patch(
            "swim_analytics.connectors.personal._request",
            side_effect=[b'{"accessToken":"test-token"}', b"not an archive"],
        ):
            with self.assertRaisesRegex(PersonalApiError, "readable FIT"):
                list(PersonalGarminSource("test-key", (42,)).activities())

    def test_http_error_identifies_step_without_showing_request(self):
        for step, responses in (
            ("token exchange", [HTTPError("private-url", 404, "Not Found", {}, None)]),
            ("activity download", [
                io.BytesIO(b'"fake.header.signature"'),
                HTTPError("private-url", 404, "Not Found", {}, None),
            ]),
        ):
            with (
                self.subTest(step=step),
                patch("swim_analytics.connectors.personal.build_opener") as opener,
            ):
                opener.return_value.open.side_effect = responses
                with self.assertRaisesRegex(PersonalApiError, f"{step} returned HTTP 404") as error:
                    list(PersonalGarminSource("test-key", (42,)).activities())
                self.assertNotIn("private-url", str(error.exception))

    def test_sync_resumes_after_failure_and_skips_archived_downloads(self):
        payload = synthetic_fit()
        page_one = b'[{"activityId":42}]'
        page_two = b'[{"activityId":43}]'
        first_run = [
            b'"fake.token.signature"', page_one, payload, page_two,
            PersonalApiError("Synthetic interrupted download"),
        ]
        retry = [b'"fake.token.signature"', page_one, page_two, payload, b'[]']
        with tempfile.TemporaryDirectory() as folder:
            argv = ["swim-analytics", "--data-dir", folder, "sync-garmin"]
            with (
                patch("sys.argv", argv),
                patch.dict(os.environ, {"GARMIN_PERSONAL_API_KEY": "test-key"}),
                patch("swim_analytics.connectors.personal._request", side_effect=first_run),
                contextlib.redirect_stderr(io.StringIO()),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    main()
            with (
                patch("sys.argv", argv),
                patch.dict(os.environ, {"GARMIN_PERSONAL_API_KEY": "test-key"}),
                patch(
                    "swim_analytics.connectors.personal._request", side_effect=retry
                ) as request,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(), 0)
            paths = [call.args[0] for call in request.call_args_list]
            self.assertNotIn("/download-service/files/activity/42", paths)
            self.assertIn("/download-service/files/activity/43", paths)
            self.assertIn("activitySubType=lap_swimming&start=1&limit=99", paths[2])
            self.assertEqual(
                archived_activity_ids(Path(folder), "garmin:personal"), {"42", "43"}
            )

    def test_key_loads_from_owner_only_dotenv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("GARMIN_PERSONAL_API_KEY=test-key\n")
            path.chmod(0o600)
            with (
                patch("swim_analytics.cli.Path", return_value=path),
                patch.dict(os.environ, clear=True),
            ):
                self.assertEqual(_configured_key(), "test-key")
                path.chmod(0o644)
                with self.assertRaisesRegex(PersonalApiError, "chmod 600"):
                    _configured_key()
