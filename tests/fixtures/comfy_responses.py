"""Mock API response fixtures for ComfyCloud endpoints."""

import struct
import zlib

PROMPT_ID = "abc-123-def"

# -- Submit endpoint --
SUBMIT_RESPONSE = {"prompt_id": PROMPT_ID}

# -- Status endpoint --
STATUS_PENDING = {"status": "pending"}
STATUS_RUNNING = {"status": "running"}
STATUS_SUCCESS = {"status": "success"}
STATUS_COMPLETED = {"status": "completed"}
STATUS_FAILED = {"status": "failed"}
STATUS_CANCELLED = {"status": "cancelled"}

# -- History endpoint --
HISTORY_RESPONSE = {
    PROMPT_ID: {
        "outputs": {
            "9": {
                "images": [
                    {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
                ]
            }
        }
    }
}


def _make_tiny_png() -> bytes:
    """Generate a valid 1x1 red pixel PNG (smallest valid PNG)."""
    # IHDR: 1x1, 8-bit RGBA
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc & 0xFFFFFFFF)

    # IDAT: single row, filter byte 0, then RGBA red pixel
    raw_row = b"\x00\xff\x00\x00\xff"  # filter=0, R=255, G=0, B=0, A=255
    compressed = zlib.compress(raw_row)
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    idat = (
        struct.pack(">I", len(compressed))
        + b"IDAT"
        + compressed
        + struct.pack(">I", idat_crc & 0xFFFFFFFF)
    )

    # IEND
    iend_crc = zlib.crc32(b"IEND")
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


TINY_PNG = _make_tiny_png()
