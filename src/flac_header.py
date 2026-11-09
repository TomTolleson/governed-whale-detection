"""Parse FLAC metadata blocks from the first bytes of a file (no audio decoding).

FLAC layout: the 4-byte magic "fLaC", then metadata blocks. Each block has a
4-byte header: 1 bit "last block" flag, 7 bits block type, 24 bits length.
Block 0 (STREAMINFO, 34 bytes) holds sample rate, channels, bits per sample
and the total number of samples, so duration = total_samples / sample_rate.
"""

import re
import struct

BLOCK_TYPES = {0: "STREAMINFO", 1: "PADDING", 2: "APPLICATION", 3: "SEEKTABLE",
               4: "VORBIS_COMMENT", 5: "CUESHEET", 6: "PICTURE"}


def parse_streaminfo(b: bytes) -> dict:
    min_block, max_block = struct.unpack(">HH", b[0:4])
    # bytes 10..17: 20 bits sample rate, 3 bits channels-1, 5 bits bps-1, 36 bits total samples
    x = int.from_bytes(b[10:18], "big")
    sample_rate = x >> 44
    channels = ((x >> 41) & 0x7) + 1
    bits_per_sample = ((x >> 36) & 0x1F) + 1
    total_samples = x & 0xFFFFFFFFF
    return {
        "sample_rate": sample_rate, "channels": channels, "bits_per_sample": bits_per_sample,
        "total_samples": total_samples, "min_block": min_block, "max_block": max_block,
        "duration_s": total_samples / sample_rate if sample_rate else None,
        "md5": b[18:34].hex(),
    }


def parse_vorbis_comment(b: bytes) -> dict:
    # Vorbis comment lengths are little-endian (unlike the rest of FLAC).
    n = struct.unpack("<I", b[0:4])[0]
    vendor = b[4:4 + n].decode("utf-8", "replace")
    pos = 4 + n
    count = struct.unpack("<I", b[pos:pos + 4])[0]
    pos += 4
    comments = []
    for _ in range(count):
        ln = struct.unpack("<I", b[pos:pos + 4])[0]
        comments.append(b[pos + 4:pos + 4 + ln].decode("utf-8", "replace"))
        pos += 4 + ln
    return {"vendor": vendor, "comments": comments}


def printable_strings(b: bytes, min_len=6):
    return [s.decode("ascii") for s in re.findall(rb"[\x20-\x7e]{%d,}" % min_len, b)]


def parse_flac_header(data: bytes) -> dict:
    """Parse all metadata blocks contained in `data` (a prefix of a FLAC file).

    Blocks that run past the end of `data` are reported with truncated=True.
    """
    if data[:4] != b"fLaC":
        raise ValueError("not a FLAC file (missing fLaC magic)")
    pos, blocks, info = 4, [], {}
    while pos + 4 <= len(data):
        hdr = data[pos]
        last, btype = bool(hdr & 0x80), hdr & 0x7F
        length = int.from_bytes(data[pos + 1:pos + 4], "big")
        body = data[pos + 4:pos + 4 + length]
        block = {"type": BLOCK_TYPES.get(btype, f"RESERVED_{btype}"), "length": length,
                 "truncated": len(body) < length}
        if btype == 0:
            info = parse_streaminfo(body)
        elif btype == 4 and not block["truncated"]:
            block.update(parse_vorbis_comment(body))
        elif btype == 2:
            block["app_id"] = body[:4].decode("ascii", "replace")
            block["strings"] = printable_strings(body[4:])[:20]
        blocks.append(block)
        pos += 4 + length
        if last:
            break
    return {"streaminfo": info, "blocks": blocks, "audio_offset": pos}
