"""Read PNG EXIF chunks without Pillow's getexif fallback decoding IDAT pixels."""

import struct
import zlib

from datelier.inspection.references.types import AssetIdentity


def exif_chunk(asset: AssetIdentity) -> bytes | None:
    with asset.path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG header")
        while stream.tell() + 12 <= asset.size:
            length, name = struct.unpack(">I4s", stream.read(8))
            if stream.tell() + length + 4 > asset.size:
                raise ValueError("Truncated PNG metadata chunk")
            if name == b"eXIf":
                if length > 1024 * 1024:
                    raise ValueError("PNG EXIF metadata exceeds 1 MiB")
                data = stream.read(length)
                checksum = struct.unpack(">I", stream.read(4))[0]
                if zlib.crc32(name + data) != checksum:
                    raise ValueError("Invalid PNG EXIF checksum")
                return b"Exif\x00\x00" + data
            stream.seek(length + 4, 1)
            if name == b"IEND":
                break
    return None
