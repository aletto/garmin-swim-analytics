"""Read-only adapter for the Garmin Connect Personal API."""

import io
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

from .base import FitActivity

HOST = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
SEARCH_PATH = "/activitylist-service/activities/search/activities"
PAGE_SIZE = 99
MAX_DOWNLOAD = 32 * 1024 * 1024


class PersonalApiError(RuntimeError):
    """Safe to display without response bodies, credentials or activity IDs."""


class _NoRedirect(HTTPRedirectHandler):
    # Do not forward Authorization to a redirected destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl) -> None:  # type: ignore[no-untyped-def]
        return None


def _request(path: str, authorization: str, method: str, limit: int) -> bytes:
    request = Request(
        HOST + path, headers={"Authorization": authorization}, method=method
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=30) as response:
            body: bytes = response.read(limit + 1)
    except HTTPError as exc:
        if path == TOKEN_PATH:
            step = "token exchange"
        elif path.startswith(SEARCH_PATH):
            step = "activity search"
        else:
            step = "activity download"
        message = f"Garmin {step} returned HTTP {exc.code}."
        if exc.code == 404 and step == "activity download":
            message += " Use the activity ID from a pool swim in the same Garmin account as the API key."
        raise PersonalApiError(message) from None
    except (URLError, OSError):
        raise PersonalApiError("Could not reach the Garmin Personal API.") from None
    if len(body) > limit:
        raise PersonalApiError("Garmin response exceeded the size limit.")
    return body


def _access_token(key: str) -> str:
    body = _request(TOKEN_PATH, f"ApiKey {key}", "POST", 64 * 1024)
    try:
        text = body.decode("utf-8-sig").strip()
    except UnicodeError:
        raise PersonalApiError("Garmin returned an unreadable token response.") from None
    try:
        result = json.loads(text)
    except ValueError:
        # Some token endpoints return a compact JWT directly as text.
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}", text):
            raise PersonalApiError(
                "Garmin returned an unexpected token format (expected JSON or a compact JWT)."
            ) from None
        result = text
    token = (result.get("access_token") or result.get("accessToken")) if isinstance(result, dict) else result
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", token):
        raise PersonalApiError("Garmin's token response did not contain an access token.")
    return token


def _fit_bytes(body: bytes) -> bytes:
    if body[8:12] == b".FIT":
        return body
    try:
        with ZipFile(io.BytesIO(body)) as archive:
            members = [
                item for item in archive.infolist()
                if not item.is_dir() and item.filename.lower().endswith(".fit")
            ]
            if len(members) != 1 or members[0].file_size > MAX_DOWNLOAD:
                raise PersonalApiError("Expected one FIT file within the download size limit.")
            return archive.read(members[0])
    except (BadZipFile, NotImplementedError, RuntimeError) as exc:
        if isinstance(exc, PersonalApiError):
            raise
        raise PersonalApiError("Garmin did not return a readable FIT archive.") from None


def _pool_activity_ids(token: str) -> Iterator[int]:
    offset = 0
    seen: set[int] = set()
    while True:
        query = urlencode({"activitySubType": "lap_swimming", "start": offset, "limit": PAGE_SIZE})
        body = _request(f"{SEARCH_PATH}?{query}", f"Bearer {token}", "GET", MAX_DOWNLOAD)
        try:
            page = json.loads(body)
        except ValueError:
            raise PersonalApiError("Garmin returned an unreadable activity page.") from None
        if not isinstance(page, list):
            raise PersonalApiError("Garmin returned an unexpected activity page.")
        if not page:
            return

        new_ids = []
        for row in page:
            activity_id = row.get("activityId") if isinstance(row, dict) else None
            if type(activity_id) is not int or not 0 < activity_id <= 2**63 - 1:
                raise PersonalApiError("A Garmin activity summary did not contain a valid ID.")
            if activity_id not in seen:
                seen.add(activity_id)
                new_ids.append(activity_id)
        if not new_ids:
            raise PersonalApiError("Garmin repeated an activity page. Retry the sync.")
        yield from new_ids
        offset += len(page)


@dataclass(frozen=True)
class PersonalGarminSource:
    api_key: str = field(repr=False)
    activity_ids: tuple[int, ...] | None = None
    archived_ids: frozenset[str] = frozenset()

    def activities(self) -> Iterator[FitActivity]:
        token = _access_token(self.api_key)
        ids = _pool_activity_ids(token) if self.activity_ids is None else iter(self.activity_ids)
        for activity_id in ids:
            if str(activity_id) in self.archived_ids:
                continue
            body = _request(
                f"/download-service/files/activity/{activity_id}",
                f"Bearer {token}", "GET", MAX_DOWNLOAD,
            )
            yield FitActivity(_fit_bytes(body), str(activity_id))
