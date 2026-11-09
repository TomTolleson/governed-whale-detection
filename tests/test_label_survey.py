import json
from datetime import date, datetime, timedelta, timezone

import pytest

from src.label_survey import LISTING_PATH, file_intervals, hours_per_day, parse_start

UTC = timezone.utc

# Real file names from the bucket listing, one per naming variant.
REAL_NAMES = [
    # deployments 01-03: YYYYMMDDTHHMMSSZ, with optional suffixes
    ("SanctSound_SB01_01_1678032935_20181112T190000Z_Post-Deployment.flac", datetime(2018, 11, 12, 19, 0, 0)),
    ("SanctSound_SB01_01_1678032935_20181113T002444Z.flac", datetime(2018, 11, 13, 0, 24, 44)),
    ("SanctSound_SB01_01_1678032935_20181202T071900Z_Post-clip.flac", datetime(2018, 12, 2, 7, 19, 0)),
    ("SanctSound_SB01_01_1678032935_20190128T161934Z_Pre-Retrieval.flac", datetime(2019, 1, 28, 16, 19, 34)),
    ("SanctSound_SB02_01_1677778970_20190128T162052Z_Pre-Retrieval_Post-clip.flac", datetime(2019, 1, 28, 16, 20, 52)),
    ("SanctSound_SB01_02_671404073_20190128T233033Z.flac", datetime(2019, 1, 28, 23, 30, 33)),
    ("SanctSound_SB02_03_67403784_20190402T200002Z.flac", datetime(2019, 4, 2, 20, 0, 2)),
    # deployments 04+: YYMMDDHHMMSS (serial number length varies)
    ("SanctSound_SB01_04_1678032935_190601180000.flac", datetime(2019, 6, 1, 18, 0, 0)),
    ("SanctSound_SB01_05_67678214_190802190000.flac", datetime(2019, 8, 2, 19, 0, 0)),
    ("SanctSound_SB02_07_805867544_191206170000.flac", datetime(2019, 12, 6, 17, 0, 0)),
    ("SanctSound_SB03_12_1677758490_200917150500.flac", datetime(2020, 9, 17, 15, 5, 0)),
]


@pytest.mark.parametrize("name,expected", REAL_NAMES)
def test_parse_real_names(name, expected):
    assert parse_start(name) == expected.replace(tzinfo=UTC)


def test_serial_number_is_not_mistaken_for_a_date():
    # A 10-digit serial like 1678032935 must not be parsed as part of the timestamp.
    assert parse_start("SanctSound_SB01_04_1678032935_190601180000.flac").year == 2019


@pytest.mark.parametrize("bad", [
    "SanctSound_SB01_04_1678032935_1906011800.flac",   # too few digits
    "SanctSound_SB01_01_1678032935_20181112T190000.flac",  # missing Z
    "SanctSound_SB01_01.json",
])
def test_unrecognised_names_raise(bad):
    with pytest.raises(ValueError):
        parse_start(bad)


@pytest.mark.skipif(not LISTING_PATH.exists(), reason="run `python -m src.label_survey fetch` first")
def test_every_listed_file_parses():
    listing = json.loads(LISTING_PATH.read_text())
    names = [n for files in listing.values() for n, _ in files]
    assert len(names) > 12000
    for n in names:
        parse_start(n)


def test_hours_split_across_midnight():
    start = datetime(2019, 6, 1, 22, 0, tzinfo=UTC)
    hpd = hours_per_day([(start, start + timedelta(hours=4), False)])
    assert hpd == {date(2019, 6, 1): 2.0, date(2019, 6, 2): 2.0}


def test_file_intervals_cap_and_last_file():
    # Three on-schedule 4 h files, then one that started late (6 h gap), then a last file.
    names = [
        ("x_190601000000.flac", 100), ("x_190601040000.flac", 100),
        ("x_190601080000.flac", 100), ("x_190601120000.flac", 100),
        ("x_190601180000.flac", 50),
    ]
    iv, nominal = file_intervals(names)
    assert nominal == 4 * 3600
    durations = [(b - a).total_seconds() / 3600 for a, b, _ in iv]
    assert durations[:4] == [4, 4, 4, 4]        # 6 h interval capped at 4 h
    assert durations[4] == pytest.approx(2.0)  # last file: 50 bytes at 100 bytes / 4 h
    assert [g for *_, g in iv] == [False, False, False, True, False]
