"""Unit tests for RecurrenceRule math."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from growth.domain.reminders import RecurrenceFrequency, RecurrenceRule

D = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def _rule(**kw: object) -> RecurrenceRule:
    defaults: dict[str, object] = {"freq": RecurrenceFrequency.DAILY}
    defaults.update(kw)
    return RecurrenceRule(**defaults)  # type: ignore[arg-type]


class TestDaily:
    def test_next_day(self) -> None:
        r = _rule()
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

    def test_interval(self) -> None:
        r = _rule(interval=3)
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 15, 9, 0, tzinfo=UTC)


class TestWeekly:
    def test_next_week(self) -> None:
        r = _rule(freq=RecurrenceFrequency.WEEKLY)
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 19, 9, 0, tzinfo=UTC)

    def test_interval(self) -> None:
        r = _rule(freq=RecurrenceFrequency.WEEKLY, interval=2)
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 26, 9, 0, tzinfo=UTC)


class TestMonthly:
    def test_same_day_next_month(self) -> None:
        r = _rule(freq=RecurrenceFrequency.MONTHLY)
        assert r.next_occurrence(D, 1) == datetime(2026, 9, 12, 9, 0, tzinfo=UTC)

    def test_year_rollover(self) -> None:
        r = _rule(freq=RecurrenceFrequency.MONTHLY)
        dec = datetime(2026, 12, 31, 9, 0, tzinfo=UTC)
        assert r.next_occurrence(dec, 1) == datetime(2027, 1, 31, 9, 0, tzinfo=UTC)

    def test_day_clamped_to_february(self) -> None:
        r = _rule(freq=RecurrenceFrequency.MONTHLY)
        jan31 = datetime(2026, 1, 31, 9, 0, tzinfo=UTC)
        assert r.next_occurrence(jan31, 1) == datetime(2026, 2, 28, 9, 0, tzinfo=UTC)

    def test_day_clamped_leap_year(self) -> None:
        r = _rule(freq=RecurrenceFrequency.MONTHLY)
        jan31 = datetime(2024, 1, 31, 9, 0, tzinfo=UTC)
        assert r.next_occurrence(jan31, 1) == datetime(2024, 2, 29, 9, 0, tzinfo=UTC)


class TestBounds:
    def test_until_not_reached(self) -> None:
        until = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)
        r = _rule(until=until)
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

    def test_until_exhausted(self) -> None:
        until = datetime(2026, 8, 13, 8, 0, tzinfo=UTC)
        r = _rule(until=until)
        assert r.next_occurrence(D, 1) is None

    def test_until_inclusive_boundary(self) -> None:
        until = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
        r = _rule(until=until)
        assert r.next_occurrence(D, 1) == datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

    def test_count_not_reached(self) -> None:
        r = _rule(count=5)
        assert r.next_occurrence(D, 3) == datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

    def test_count_reached(self) -> None:
        r = _rule(count=2)
        assert r.next_occurrence(D, 2) is None

    def test_count_exceeded(self) -> None:
        r = _rule(count=2)
        assert r.next_occurrence(D, 3) is None


class TestValidation:
    def test_interval_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            _rule(interval=0)

    def test_count_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            _rule(count=0)


class TestImmutability:
    def test_frozen(self) -> None:
        r = _rule()
        with pytest.raises(FrozenInstanceError):
            r.interval = 2  # type: ignore[misc]
