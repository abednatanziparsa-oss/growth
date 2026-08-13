"""Unit tests for the iCalendar (.ics) projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from growth.infrastructure.projections.calendar import EventPayload
from growth.infrastructure.projections.ics import (
    FOLD_LIMIT,
    PRODID,
    IcsProjection,
    _escape,
    _fold,
    _format_dt,
)


def _event(
    *,
    summary: str = "Study Physics",
    start: str = "2026-08-14T06:30:00+00:00",
    end: str = "2026-08-14T07:00:00+00:00",
    uid: str = "abc-123",
) -> EventPayload:
    return EventPayload(
        summary=summary,
        start=start,
        end=end,
        description="Growth OS reminder -> space:space",
        uid=uid,
    )


class TestEscape:
    def test_escapes_special_characters(self) -> None:
        assert _escape(r"a\b;c,d") == r"a\\b\;c\,d"

    def test_escapes_newlines(self) -> None:
        assert _escape("line1\nline2\r\nline3") == "line1\\nline2\\nline3"


class TestFold:
    def test_short_line_unchanged(self) -> None:
        line = "SUMMARY:Short"
        assert _fold(line) == line

    def test_long_line_folds_at_75_octets(self) -> None:
        summary = "S" * 100
        folded = _fold(f"SUMMARY:{summary}")
        parts = folded.split("\r\n ")
        assert len(parts) > 1
        for part in parts:
            assert len(part.encode("utf-8")) <= FOLD_LIMIT

    def test_multibyte_folding_is_byte_aware(self) -> None:
        summary = "درس" * 30  # 2-3 bytes per char in UTF-8
        folded = _fold(f"SUMMARY:{summary}")
        for part in folded.split("\r\n "):
            assert len(part.encode("utf-8")) <= FOLD_LIMIT


class TestFormatDt:
    def test_formats_utc_basic(self) -> None:
        dt = datetime(2026, 8, 14, 6, 30, tzinfo=UTC)
        assert _format_dt(dt) == "20260814T063000Z"

    def test_converts_timezone_to_utc(self) -> None:
        tehran = timezone(timedelta(hours=3, minutes=30))
        dt = datetime(2026, 8, 14, 10, 0, tzinfo=tehran)
        assert _format_dt(dt) == "20260814T063000Z"

    def test_naive_datetime_assumed_utc(self) -> None:
        assert _format_dt(datetime(2026, 8, 14, 6, 30)) == "20260814T063000Z"


class TestIcsProjection:
    def test_render_wraps_calendar(self) -> None:
        text = IcsProjection().render([_event()])
        lines = text.split("\r\n")
        assert lines[0] == "BEGIN:VCALENDAR"
        assert lines[1] == "VERSION:2.0"
        assert lines[2] == f"PRODID:{PRODID}"
        assert lines[-2] == "END:VCALENDAR"
        assert text.endswith("\r\n")

    def test_render_event_fields(self) -> None:
        text = IcsProjection().render([_event(summary="Math, review; ch.1")])
        assert "UID:abc-123@growth.local" in text
        assert "DTSTART:20260814T063000Z" in text
        assert "DTEND:20260814T070000Z" in text
        assert "SUMMARY:Math\\, review\\; ch.1" in text
        assert "DESCRIPTION:Growth OS reminder -> space:space" in text
        assert text.count("BEGIN:VEVENT") == 1

    def test_render_no_events(self) -> None:
        text = IcsProjection().render([])
        assert text.startswith("BEGIN:VCALENDAR")
        assert "BEGIN:VEVENT" not in text
        assert text.endswith("END:VCALENDAR\r\n")

    def test_uid_is_stable_per_event(self) -> None:
        text = IcsProjection().render([_event(uid="uid-1"), _event(uid="uid-2")])
        assert "UID:uid-1@growth.local" in text
        assert "UID:uid-2@growth.local" in text
        assert text.count("BEGIN:VEVENT") == 2

    def test_multibyte_summary_renders_and_folds(self) -> None:
        text = IcsProjection().render([_event(summary="مرور فیزیک و ریاضیات" * 4)])
        assert "SUMMARY:" in text
        assert text.count("BEGIN:VEVENT") == 1
