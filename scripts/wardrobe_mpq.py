"""Read-only identity checks for classic MPQ archives used by the wardrobe repair.

This module reads numeric hash/block tables rather than mpqcli's locale labels:
that tool displays both neutral LCID 0 and US English LCID 0x0409 as ``enUS``.
No game assets are distributed here, and these routines never modify archives.

Supported layouts are MPQ format 0/1 (also called archive versions 1/2), with
the MPQ header at byte zero and ordinary encrypted hash/block tables. Embedded
archives, extended block tables and later MPQ formats require separate review.
This is deliberately an identity/bounds reader, not a general MPQ extractor or
a validation of the content of every compressed member.
"""

from collections import Counter
from pathlib import Path
import struct


_MASK = 0xFFFFFFFF
_MAX_TABLE_ENTRIES = 1 << 22  # Bounded allocation for an untrusted header.
_EXISTS = 0x80000000


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _crypt_table():
    values = [0] * 0x500
    seed = 0x100001
    for low in range(256):
        for high in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            upper = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            values[high * 256 + low] = upper | (seed & 0xFFFF)
    return tuple(values)


_CRYPT = _crypt_table()


def name_hash(name, kind):
    """Return an integer MPQ name hash (kinds 0..3); names must be ASCII."""
    _require(isinstance(kind, int) and 0 <= kind <= 3, "Unsupported MPQ hash kind")
    _require(isinstance(name, str) and "\x00" not in name, "Invalid MPQ member name")
    try:
        raw = name.replace("/", "\\").encode("ascii").upper()
    except UnicodeEncodeError as error:
        raise ValueError("Non-ASCII MPQ member names require separate review") from error
    first, second = 0x7FED7FED, 0xEEEEEEEE
    for char in raw:
        first = (_CRYPT[kind * 256 + char] ^ (first + second)) & _MASK
        second = (char + first + second + (second << 5) + 3) & _MASK
    return first


def _decrypt(data, key):
    _require(len(data) % 4 == 0, "Truncated MPQ encrypted table")
    result = bytearray(len(data))
    seed = 0xEEEEEEEE
    for index, (word,) in enumerate(struct.iter_unpack("<I", data)):
        seed = (seed + _CRYPT[0x400 + (key & 255)]) & _MASK
        plain = (word ^ ((key + seed) & _MASK)) & _MASK
        key = (((((~key) & _MASK) << 21) + 0x11111111) | (key >> 11)) & _MASK
        seed = (plain + seed + (seed << 5) + 3) & _MASK
        struct.pack_into("<I", result, index * 4, plain)
    return result


def _read_exact(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    _require(len(data) == size, "MPQ changed or was truncated while reading")
    return data


def _table_bounds(offset, count, header_size, file_size, label):
    _require(0 <= count <= _MAX_TABLE_ENTRIES, f"Unsupported {label} table size")
    if count:
        _require(header_size <= offset <= file_size
                 and count * 16 <= file_size - offset,
                 f"MPQ {label} table lies outside the archive")


def numeric_inventory(path):
    """Return active hash rows with numeric identity and corresponding block data.

    Each dictionary contains integer hash1, hash2, locale, platform, reserved,
    block, hash_slot, offset, compressed_size, size and flags fields. Deleted
    and never-used hash slots are excluded. LCIDs are not converted to labels.
    Unsupported layouts and inconsistent bounds raise ValueError.
    """
    path = Path(path)
    with path.open("rb") as stream:
        stream.seek(0, 2)
        file_size = stream.tell()
        _require(file_size >= 32, "Truncated MPQ header")
        header = _read_exact(stream, 0, 32)
        (magic, header_size, archive_size, version, sector_shift,
         hash_offset, block_offset, hash_count, block_count) = struct.unpack("<4s2I2H4I", header)
        _require(magic == b"MPQ\x1a", "Expected an MPQ header at byte zero")
        _require(version in (0, 1), "Unsupported MPQ format version")
        expected_size = 32 if version == 0 else 44
        _require(header_size == expected_size, "Unsupported MPQ header length")
        _require(file_size >= header_size, "Truncated extended MPQ header")
        _require(sector_shift <= 16, "Unsupported MPQ sector size")
        if version == 1:
            extended_blocks, hash_high, block_high = struct.unpack(
                "<Q2H", _read_exact(stream, 32, 12))
            _require(extended_blocks == 0, "Extended MPQ block tables require separate review")
            hash_offset |= hash_high << 32
            block_offset |= block_high << 32
        else:
            _require(header_size <= archive_size <= file_size,
                     "Invalid classic MPQ archive size")
        _require(hash_count > 0 and hash_count & (hash_count - 1) == 0,
                 "Invalid MPQ hash table capacity")
        _table_bounds(hash_offset, hash_count, header_size, file_size, "hash")
        _table_bounds(block_offset, block_count, header_size, file_size, "block")
        hash_end, block_end = hash_offset + hash_count * 16, block_offset + block_count * 16
        _require(not block_count or hash_end <= block_offset or block_end <= hash_offset,
                 "Overlapping MPQ hash and block tables")
        hashes = _decrypt(_read_exact(stream, hash_offset, hash_count * 16), name_hash("(hash table)", 3))
        blocks = _decrypt(_read_exact(stream, block_offset, block_count * 16), name_hash("(block table)", 3))

    rows = []
    for slot, (first, second, locale, platform, reserved, block) in enumerate(
            struct.iter_unpack("<IIHBBI", hashes)):
        if block in (0xFFFFFFFF, 0xFFFFFFFE):
            continue
        _require(block < block_count, "Active MPQ hash references a missing block")
        offset, compressed_size, size, flags = struct.unpack_from("<4I", blocks, block * 16)
        _require(flags & _EXISTS, "Active MPQ hash references a nonexistent file")
        _require(offset <= file_size and compressed_size <= file_size - offset,
                 "MPQ member lies outside the archive")
        if compressed_size:
            _require(offset >= header_size, "MPQ member overlaps the header")
            end = offset + compressed_size
            _require(end <= hash_offset or offset >= hash_end,
                     "MPQ member overlaps the hash table")
            _require(not block_count or end <= block_offset or offset >= block_end,
                     "MPQ member overlaps the block table")
        rows.append(dict(hash1=first, hash2=second, locale=locale, platform=platform,
                         reserved=reserved, block=block, hash_slot=slot, offset=offset,
                         compressed_size=compressed_size, size=size, flags=flags))
    return rows


def member_rows(rows, name):
    """Find every numeric identity for a name, retaining any locale variants."""
    first, second = name_hash(name, 1), name_hash(name, 2)
    return [row for row in rows if row["hash1"] == first and row["hash2"] == second]


def verify_identity(before_path, after_path):
    """Require unchanged identity multiplicities, including raw locale/platform.

    Blocks and slots may move during a valid MPQ rewrite; callers must separately
    compare unaffected compressed payloads and verify replacement content hashes.
    """
    before, after = numeric_inventory(before_path), numeric_inventory(after_path)
    fields = ("hash1", "hash2", "locale", "platform", "reserved")
    keys = lambda rows: Counter(tuple(row[field] for field in fields) for row in rows)
    _require(keys(before) == keys(after), "MPQ numeric member identities changed")
    return dict(passed=True, identity_multiset_equal=True, before_members=len(before),
                after_members=len(after),
                locale_counts={str(key): value for key, value in sorted(
                    Counter(row["locale"] for row in after).items())})
