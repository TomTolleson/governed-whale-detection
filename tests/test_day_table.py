import struct

import pandas as pd
import pytest

from src.day_table import build_day_table, exclusion_reason
from src.flac_header import parse_flac_header


def files(*starts, size=100):
    """Short-name (04+) audio files starting at the given YYMMDDHHMMSS stamps."""
    return [[f"SanctSound_SB01_04_1678032935_{s}.flac", size] for s in starts]


def labels(rows):
    return pd.DataFrame(rows, columns=["ISOStartTime", "Presence"])


@pytest.fixture
def table():
    # Deployment 04: 4 h files from 2019-06-01 16:00 to 2019-06-03 12:00 (last file 4 h by size).
    starts_a = [f"1906{d:02d}{h:02d}0000" for d in (1, 2, 3) for h in range(0, 24, 4)
                if (d, h) >= (1, 16) and (d, h) <= (3, 12)]
    # Deployment 05 starts the same day deployment 04 ends (changeover day 2019-06-03).
    starts_b = ["190603200000", "190604000000", "190604040000", "190604080000"]
    listing = {"sb01_04": files(*starts_a), "sb01_05": files(*starts_b)}
    lab = {
        "sb01_04": labels([("2019-05-31", 0),   # labelled, but no audio at all
                           ("2019-06-01", 1),   # 8 h (partial)
                           ("2019-06-02", 1),   # 24 h
                           ("2019-06-03", 0)]),  # 16 h, changeover
        "sb01_05": labels([("2019-06-03", 1),   # 4 h, changeover
                           ("2019-06-04", 0)]),  # 12 h (last file sized as 4 h)
    }
    return build_day_table(lab, listing).set_index(["deployment", "date"])


def test_columns_match_brief(table):
    assert list(table.reset_index().columns) == [
        "deployment", "date",  # moved to the index by the fixture
        "site", "label", "audio_hours", "is_partial_day", "no_audio", "is_changeover_day", "eligible"]


def test_audio_hours(table):
    assert table.loc[("04", "2019-05-31"), "audio_hours"] == 0
    assert table.loc[("04", "2019-06-01"), "audio_hours"] == 8
    assert table.loc[("04", "2019-06-02"), "audio_hours"] == 24
    assert table.loc[("04", "2019-06-03"), "audio_hours"] == 16
    assert table.loc[("05", "2019-06-03"), "audio_hours"] == 4


def test_no_audio_day_is_not_eligible(table):
    r = table.loc[("04", "2019-05-31")]
    assert r["no_audio"] and not r["eligible"] and not r["is_partial_day"]
    assert exclusion_reason(r) == "no_audio"


def test_full_day_is_eligible(table):
    r = table.loc[("04", "2019-06-02")]
    assert r["eligible"] and not r["is_partial_day"] and not r["no_audio"]
    assert exclusion_reason(r) is None


def test_partial_day_under_20h_is_excluded(table):
    r = table.loc[("04", "2019-06-01")]
    assert r["is_partial_day"] and not r["eligible"]
    assert exclusion_reason(r) == "audio_hours_lt_20"


def test_changeover_flag_on_both_deployments_only(table):
    assert table.loc[("04", "2019-06-03"), "is_changeover_day"]
    assert table.loc[("05", "2019-06-03"), "is_changeover_day"]
    assert not table.loc[("04", "2019-06-02"), "is_changeover_day"]


def test_label_is_kept_unchanged(table):
    assert table.loc[("05", "2019-06-03"), "label"] == 1
    assert table.loc[("04", "2019-06-03"), "label"] == 0


@pytest.mark.parametrize("hours,expected", [(19.999, False), (20.0, True), (23.5, True)])
def test_threshold_is_inclusive_at_20h(hours, expected):
    # 4 h files; the day's first file starts at 24 - hours.
    start_h = 24 - hours
    hh, mm = int(start_h), round((start_h % 1) * 60 * 60)
    first = f"190601{hh:02d}{mm // 60:02d}{mm % 60:02d}"
    later = [f"190602{h:02d}0000" for h in range(0, 24, 4)]
    nxt = [f"190601{h:02d}0000" for h in range(0, 24, 4) if h > start_h]
    listing = {"sb01_04": files(first, *nxt, *later)}
    t = build_day_table({"sb01_04": labels([("2019-06-01", 1)])}, listing)
    assert t.loc[0, "audio_hours"] == pytest.approx(hours, abs=1e-3)
    assert bool(t.loc[0, "eligible"]) is expected


def make_flac(sample_rate=48000, channels=1, bps=16, total=48000 * 3600, vendor=b"Lavf57.83.100"):
    x = (sample_rate << 44) | ((channels - 1) << 41) | ((bps - 1) << 36) | total
    streaminfo = struct.pack(">HH", 4096, 4096) + b"\0" * 6 + x.to_bytes(8, "big") + b"\0" * 16
    vc = struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 1) + struct.pack("<I", 7) + b"enc=abc"
    return (b"fLaC" + bytes([0]) + len(streaminfo).to_bytes(3, "big") + streaminfo
            + bytes([0x80 | 4]) + len(vc).to_bytes(3, "big") + vc)


def test_flac_streaminfo_parse():
    h = parse_flac_header(make_flac())
    si = h["streaminfo"]
    assert (si["sample_rate"], si["channels"], si["bits_per_sample"]) == (48000, 1, 16)
    assert si["duration_s"] == 3600
    assert h["blocks"][1]["vendor"] == "Lavf57.83.100"
    assert h["blocks"][1]["comments"] == ["enc=abc"]


def test_flac_truncated_block_is_flagged():
    data = make_flac()[:60]  # cut inside the VORBIS_COMMENT block
    assert parse_flac_header(data)["blocks"][1]["truncated"]


def test_not_flac_raises():
    with pytest.raises(ValueError):
        parse_flac_header(b"RIFF....WAVE")
