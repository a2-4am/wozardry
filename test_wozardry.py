#!/usr/bin/env python3

# Sources of all truth:
#
# - WOZ1 specification <https://applesaucefdc.com/woz/reference1/>
# - WOZ2 specification <https://applesaucefdc.com/woz/reference2/>
#
# There is no spec but the spec itself.

import wozardry
import pytest # https://pypi.org/project/pytest/
import argparse
import tempfile
import shutil
import io

# two valid .woz files in the repository
kValid1 = "test/valid1.woz"
kValid2 = "test/valid2.woz"

# valid WOZ1 header as string of hex
kHeader1 = "57 4F 5A 31 FF 0A 0D 0A 00 00 00 00 "

# valid WOZ2 header as string of hex
kHeader2 = "57 4F 5A 32 FF 0A 0D 0A 00 00 00 00 "

def bfh(s):
    """utility function to convert string of hex into a BytesIO stream"""
    return io.BytesIO(bytes.fromhex(s))

#----- test file parser -----

def test_parse_header():
    # incomplete header
    with pytest.raises(wozardry.WozEOFError):
        wozardry.WozDiskImage(bfh("57 4F 5A 32"))

    with pytest.raises(wozardry.WozEOFError):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 FF 0A 0D"))

    with pytest.raises(wozardry.WozEOFError):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 FF 0A 0D 0A 00 00 00"))

    # invalid signature at offset 0
    with pytest.raises(wozardry.WozHeaderError_NoWOZMarker):
        wozardry.WozDiskImage(bfh("57 4F 5A 30 00 00 00 00"))

    # invalid signature at offset 0
    with pytest.raises(wozardry.WozHeaderError_NoWOZMarker):
        wozardry.WozDiskImage(bfh("57 4F 5A 33 00 00 00 00"))

    # missing FF byte at offset 4
    with pytest.raises(wozardry.WozHeaderError_NoFF):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 00 0A 0D 0A"))

    # missing 0A byte at offset 5
    with pytest.raises(wozardry.WozHeaderError_NoLF):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 FF 0D 0D 0D"))

    # missing 0D byte at offset 6
    with pytest.raises(wozardry.WozHeaderError_NoLF):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 FF 0A 0A 0A"))

    # missing 0A byte at offset 7
    with pytest.raises(wozardry.WozHeaderError_NoLF):
        wozardry.WozDiskImage(bfh("57 4F 5A 32 FF 0A 0D 0D"))

def test_parse_info():
    # TMAP chunk before INFO chunk
    with pytest.raises(wozardry.WozINFOFormatError_MissingINFOChunk):
        wozardry.WozDiskImage(bfh(kHeader2 + "54 4D 41 50 A0 00 00 00 " + "FF "*160))

    # wrong INFO chunk size (too small)
    with pytest.raises(wozardry.WozINFOFormatError):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3B 00 00 00 " + "00 "*59))

    # wrong INFO chunk size (too big)
    with pytest.raises(wozardry.WozINFOFormatError):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3D 00 00 00 " + "00 "*61))

    # invalid version (0) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadVersion):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 00" + "00 "*59))

    # invalid version (0) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadVersion):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 00" + "00 "*59))

    # invalid version (1) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadVersion):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 01" + "00 "*59))

    # invalid version (2) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadVersion):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 02" + "00 "*59))

    # invalid disk type (0) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 00 " + "00 "*58))

    # invalid disk type (0) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 00 " + "00 "*58))

    # invalid disk type (3) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 03 " + "00 "*58))

    # invalid disk type (3) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 03 " + "00 "*58))

    # invalid write protected flag (2) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadWriteProtected):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 01 02 " + "00 "*57))

    # invalid write protected flag (2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadWriteProtected):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 02 " + "00 "*57))

    # invalid synchronized flag (2) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadSynchronized):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 01 00 02 " + "00 "*56))

    # invalid synchronized flag (2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadSynchronized):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 02 " + "00 "*56))

    # invalid cleaned flag (2) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCleaned):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 01 00 00 02 " + "00 "*55))

    # invalid cleaned flag (2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCleaned):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 02 " + "00 "*55))

    # invalid creator (bad UTF-8 bytes) in a WOZ1 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCreator):
        wozardry.WozDiskImage(bfh(kHeader1 + "49 4E 46 4F 3C 00 00 00 01 01 00 00 00 E0 80 80 " + "00 "*52))

    # invalid creator (bad UTF-8 bytes) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCreator):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 E0 80 80 " + "00 "*52))

    # invalid disk sides (0) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskSides):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "00 " + "00 "*22))

    # invalid disk sides (3) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskSides):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "03 " + "00 "*22))

    # invalid disk sides (2, when disk type = 1) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadDiskSides):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "02 " + "00 "*22))

    # invalid boot sector format (4) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadBootSectorFormat):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 04 " + "00 "*21))

    # invalid boot sector format (1, when disk type = 2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadBootSectorFormat):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 01 " + "00 "*21))

    # invalid boot sector format (2, when disk type = 2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadBootSectorFormat):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 02 " + "00 "*21))

    # invalid boot sector format (3, when disk type = 2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadBootSectorFormat):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 02 " + "00 "*21))

    # invalid optimal bit timing (23, when disk type = 1) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 17 " + "00 "*20))

    # invalid optimal bit timing (41, when disk type = 1) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 29 " + "00 "*20))

    # invalid optimal bit timing (7, when disk type = 2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 00 07 " + "00 "*20))

    # invalid optimal bit timing (25, when disk type = 2) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 00 19 " + "00 "*20))

    # invalid optimal bit timing (0, when disk type = 1) in a WOZ2 file
    # unlike other fields, this does not allow a 0 value to mean "unknown"
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 00 " + "00 "*20))

    # invalid optimal bit timing (0, when disk type = 2) in a WOZ2 file
    # unlike other fields, this does not allow a 0 value to mean "unknown"
    with pytest.raises(wozardry.WozINFOFormatError_BadOptimalBitTiming):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 02 00 00 00 " + "20 "*32 + "01 00 00 " + "00 "*20))

    # invalid compatible hardware (00000010 00000000) in a WOZ2 file
    # this field only uses the lower 9 bits (for 9 hardware models), so the 7 high bits must all be 0
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 02 " + "00 "*18))

    # invalid compatible hardware (00000100 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 04 " + "00 "*18))

    # invalid compatible hardware (00001000 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 08 " + "00 "*18))

    # invalid compatible hardware (00010000 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 10 " + "00 "*18))

    # invalid compatible hardware (00100000 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 20 " + "00 "*18))

    # invalid compatible hardware (01000000 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 40 " + "00 "*18))

    # invalid compatible hardware (10000000 00000000) in a WOZ2 file
    with pytest.raises(wozardry.WozINFOFormatError_BadCompatibleHardware):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 80 " + "00 "*18))

def test_parse_tmap():
    # missing TMAP chunk
    with pytest.raises(wozardry.WozTMAPFormatError_MissingTMAPChunk):
        wozardry.WozDiskImage(bfh(kHeader2 + "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 00 " + "00 "*18))

    # TRKS chunk before TMAP chunk
    with pytest.raises(wozardry.WozTMAPFormatError_MissingTMAPChunk):
        wozardry.WozDiskImage(
            bfh(
                kHeader2 + \
                "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 00 " + "00 "*18 + \
                "54 52 4B 53 00 00 00 00 "))

    # TMAP points to non-existent TRK in TRKS chunk
    with pytest.raises(wozardry.WozTMAPFormatError_BadTRKS):
        wozardry.WozDiskImage(
            bfh(
                kHeader2 + \
                "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 00 " + "00 "*18 + \
                "54 4D 41 50 A0 00 00 00 00 " + "FF "*159 + \
                "54 52 4B 53 00 00 00 00 "))

def test_parse_trks():
    # this constitutes a valid WOZ2 file header, valid INFO chunk,
    # valid TMAP chunk with 1 entry pointing to TRK 0 in TRKS chunk,
    # and the 4-byte TRKS chunk ID
    prefix = kHeader2 + \
        "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 00 " + "00 "*18 + \
        "54 4D 41 50 A0 00 00 00 00 " + "FF "*159 + \
        "54 52 4B 53 "

    # invalid TRKS chunk with 1 TRK entry whose starting block = 1 (must be 3+)
    with pytest.raises(wozardry.WozTRKSFormatError_BadStartingBlock):
        wozardry.WozDiskImage(bfh(prefix + "00 05 00 00 01 00 01 00 01 00 00 00  " + "00 "*1272))

    # invalid TRKS chunk with 1 TRK entry whose starting block = 2 (must be 3+)
    with pytest.raises(wozardry.WozTRKSFormatError_BadStartingBlock):
        wozardry.WozDiskImage(bfh(prefix + "00 05 00 00 02 00 01 00 01 00 00 00  " + "00 "*1272))

    # invalid TRKS chunk with 1 TRK entry whose block count = 1 but has no BITS data for the block
    with pytest.raises(wozardry.WozTRKSFormatError_BadStartingBlock):
        wozardry.WozDiskImage(bfh(prefix + "00 05 00 00 03 00 01 00 01 00 00 00  " + "FF "*1272))

    # invalid TRKS chunk with 1 TRK entry whose block count = 1 but has only partial BITS data for the block
    with pytest.raises(wozardry.WozTRKSFormatError_BadBlockCount):
        wozardry.WozDiskImage(bfh(prefix + "FF 06 00 00 03 00 01 00 01 00 00 00  " + "00 "*1272 + "FF "*511))

def test_parse_meta():
    def build_meta_chunk(key, value):
        """|key| and |value| are strings, returns string of hex bytes to feed into bfh()"""
        bkey = key.encode("utf-8")
        bvalue = value.encode("utf-8")
        return (wozardry.to_uint32(len(bkey) + len(bvalue) + 2) + bkey + b'\x09' + bvalue + b'\x0A').hex()

    # this constitutes a valid WOZ2 header, valid INFO chunk,
    # valid TMAP chunk with 0 entries, and the 4-byte META chunk ID
    prefix = kHeader2 + \
        "49 4E 46 4F 3C 00 00 00 02 01 00 00 00 " + "20 "*32 + "01 00 20 00 00 " + "00 "*18 + \
        "54 4D 41 50 A0 00 00 00 " + "FF "*160 + \
        "4D 45 54 41 "

    # valid META chunk with 0 length
    wozardry.WozDiskImage(bfh(prefix + "00 00 00 00 "))

    # invalid UTF-8
    with pytest.raises(wozardry.WozMETAFormatError_EncodingError):
        wozardry.WozDiskImage(bfh(prefix + "03 00 00 00 E0 80 80"))

    # valid language values
    for lang in wozardry.kLanguages:
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("language", lang)))

    # invalid language value
    with pytest.raises(wozardry.WozMETAFormatError_BadLanguage):
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("language", "Englush")))

    # valid requires_ram values
    for ram in wozardry.kRequiresRAM:
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("requires_ram", ram)))

    # invalid requires_ram value
    with pytest.raises(wozardry.WozMETAFormatError_BadRAM):
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("requires_ram", "0")))

    # valid requires_machine values
    for machine in wozardry.kRequiresMachine:
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("requires_machine", machine)))

    # invalid requires_machine value
    with pytest.raises(wozardry.WozMETAFormatError_BadMachine):
        wozardry.WozDiskImage(bfh(prefix + build_meta_chunk("requires_machine", "4")))

    # invalid format (duplicate key)
    bk = "language".encode("utf-8")
    bv = "English".encode("utf-8")
    chunk = bk + b"\x09" + bv + b"\x0A" + bk + b"\x09" + bv + b"\0x0A"
    chunk = (wozardry.to_uint32(len(chunk)) + chunk).hex()
    with pytest.raises(wozardry.WozMETAFormatError_DuplicateKey):
        wozardry.WozDiskImage(bfh(prefix + chunk))

    # invalid format (no tab separator between key an dvalue)
    chunk = bk + bv + b"\x0A"
    chunk = (wozardry.to_uint32(len(chunk)) + chunk).hex()
    with pytest.raises(wozardry.WozMETAFormatError_NotEnoughTabs):
        wozardry.WozDiskImage(bfh(prefix + chunk))

    # invalid format (too many tabs between key and value)
    chunk = bk + b"\x09"*2 + bv + b"\x0A"
    chunk = (wozardry.to_uint32(len(chunk)) + chunk).hex()
    with pytest.raises(wozardry.WozMETAFormatError_TooManyTabs):
        wozardry.WozDiskImage(bfh(prefix + chunk))

#----- test command-line interface -----

def test_command_verify():
    """verify a valid WOZ1/WOZ2 file and exit cleanly"""
    wozardry.parse_args(["verify", kValid1])
    wozardry.parse_args(["verify", kValid2])

def test_command_dump_woz1(capsys):
    """dump a WOZ1 file and ensure it prints expected output"""
    wozardry.parse_args(["dump", kValid1])
    captured = capsys.readouterr()
    assert "INFO:  File format version:    1" in captured.out
    assert "INFO:  Disk type:              5.25-inch (140K)" in captured.out
    assert "INFO:  Write protected:        no" in captured.out
    assert "INFO:  Tracks synchronized:    no" in captured.out
    assert "INFO:  Weakbits cleaned:       no" in captured.out
    assert "INFO:  Creator:                wozardry" in captured.out

def test_command_dump_woz2(capsys):
    """dump a WOZ2 file and ensure it prints expected output"""
    wozardry.parse_args(["dump", kValid2])
    captured = capsys.readouterr()
    assert "INFO:  File format version:    2" in captured.out
    assert "INFO:  Disk type:              5.25-inch (140K)" in captured.out
    assert "INFO:  Write protected:        no" in captured.out
    assert "INFO:  Tracks synchronized:    no" in captured.out
    assert "INFO:  Weakbits cleaned:       no" in captured.out
    assert "INFO:  Creator:                wozardry" in captured.out
    assert "INFO:  Boot sector format:     0 (unknown)" in captured.out
    assert "INFO:  Optimal bit timing:     32 (standard)" in captured.out
    assert "INFO:  Compatible hardware:    unknown" in captured.out
    assert "INFO:  Required RAM:           unknown" in captured.out
    assert "INFO:  Largest track:          0 blocks" in captured.out

def test_command_edit_info_version_1_to_2():
    """convert a WOZ1 file to WOZ2 and ensure new info fields are set to default values"""
    with tempfile.NamedTemporaryFile() as tmp:
        shutil.copy(kValid1, tmp.name)

        wozardry.parse_args(["edit", "-i", "version:2", tmp.name])
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.woz_version == 2
        assert woz.info["version"] == 2
        assert woz.info["boot_sector_format"] == 0
        assert woz.info["optimal_bit_timing"] == 32
        assert woz.info["compatible_hardware"] == []
        assert woz.info["required_ram"] == 0

def test_command_edit_info_disk_type():
    """edit a WOZ1/WOZ2 file to change the disk type"""
    # this is pathological, don't do this in real life
    def f(inputfile):
        with tempfile.NamedTemporaryFile() as tmp:
            shutil.copy(inputfile, tmp.name)

            # disk_type = 1 is ok
            wozardry.parse_args(["edit", "-i", "disk_type:1", tmp.name])
            with open(tmp.name, "rb") as tmpstream:
                woz = wozardry.WozDiskImage(tmpstream)
            assert woz.info["disk_type"] == 1

            # disk_type = 2 is ok
            wozardry.parse_args(["edit", "-i", "disk_type:2", tmp.name])
            with open(tmp.name, "rb") as tmpstream:
                woz = wozardry.WozDiskImage(tmpstream)
            assert woz.info["disk_type"] == 2

            # disk_type = 0 is not ok
            with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
                wozardry.parse_args(["edit", "-i", "disk_type:0", tmp.name])

            # disk_type = 3 is not ok
            with pytest.raises(wozardry.WozINFOFormatError_BadDiskType):
                wozardry.parse_args(["edit", "-i", "disk_type:3", tmp.name])
    f(kValid1)
    f(kValid2)

def test_command_edit_info_changing_disk_type_resets_optimal_bit_timing():
    """edit a WOZ2 file to change the disk type and ensure optimal bit timing is reset to default value"""
    # this is pathological, don't do this in real life
    with tempfile.NamedTemporaryFile() as tmp:
        shutil.copy(kValid2, tmp.name)
        wozardry.parse_args(["edit", "-i", "disk_type:2", tmp.name])
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.info["optimal_bit_timing"] == wozardry.kDefaultBitTiming[2]

def test_command_edit_info_boolean_flags():
    """edit a WOZ1/WOZ2 file to change Boolean flags in a variety of ways and ensure they change"""
    def f(inputfile):
        with tempfile.NamedTemporaryFile() as tmp:
            shutil.copy(inputfile, tmp.name)

            for flag in ("write_protected", "synchronized", "cleaned"):
                for true_value, false_value in (("1", "0"),
                                                ("yes", "no"),
                                                ("YES", "No"),
                                                ("true", "false"),
                                                ("tRuE", "FaLsE")):
                    wozardry.parse_args(["edit", "-i", "%s:%s" % (flag, true_value), tmp.name])
                    with open(tmp.name, "rb") as tmpstream:
                        woz = wozardry.WozDiskImage(tmpstream)
                    assert woz.info[flag] == True
                    wozardry.parse_args(["edit", "-i", "%s:%s" % (flag, false_value), tmp.name])
                    with open(tmp.name, "rb") as tmpstream:
                        woz = wozardry.WozDiskImage(tmpstream)
                    assert woz.info[flag] == False
    f(kValid1)
    f(kValid2)

def test_command_edit_disk_sides():
    """edit a WOZ2 file to change disk sides"""
    with tempfile.NamedTemporaryFile() as tmp:
        shutil.copy(kValid2, tmp.name)

        # this file is a 5.25-inch disk image
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.info["disk_type"] == 1
        assert woz.info["disk_sides"] == 1

        # 5.25-inch disk images can only be "1-sided"
        with pytest.raises(wozardry.WozINFOFormatError_BadDiskSides):
            wozardry.parse_args(["edit", "-i", "disk_sides:2", tmp.name])

        # now change it to a 3.5-inch disk image
        wozardry.parse_args(["edit", "-i", "disk_type:2", tmp.name])
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.info["disk_type"] == 2

        # 3.5-inch disk images can be 1- or 2-sided
        wozardry.parse_args(["edit", "-i", "disk_sides:2", tmp.name])
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.info["disk_sides"] == 2
        wozardry.parse_args(["edit", "-i", "disk_sides:1", tmp.name])
        with open(tmp.name, "rb") as tmpstream:
            woz = wozardry.WozDiskImage(tmpstream)
        assert woz.info["disk_sides"] == 1

        # ...but not 3-sided, that's silly
        with pytest.raises(wozardry.WozINFOFormatError_BadDiskSides):
            wozardry.parse_args(["edit", "-i", "disk_sides:3", tmp.name])

def test_command_edit_language():
    """edit a WOZ1/WOZ2 file to change the metadata language field"""
    def f(inputfile):
        with tempfile.NamedTemporaryFile() as tmp:
            shutil.copy(inputfile, tmp.name)

            for lang in wozardry.kLanguages:
                wozardry.parse_args(["edit", "-m", "language:%s" % lang, tmp.name])
                with open(tmp.name, "rb") as tmpstream:
                    woz = wozardry.WozDiskImage(tmpstream)
                assert woz.meta["language"] == lang
    f(kValid1)
    f(kValid2)

def test_command_edit_requires_ram():
    """edit a WOZ1/WOZ2 file to change the metadata requires_ram field"""
    def f(inputfile):
        with tempfile.NamedTemporaryFile() as tmp:
            shutil.copy(inputfile, tmp.name)

            for ram in wozardry.kRequiresRAM:
                wozardry.parse_args(["edit", "-m", "requires_ram:%s" % ram, tmp.name])
                with open(tmp.name, "rb") as tmpstream:
                    woz = wozardry.WozDiskImage(tmpstream)
                assert woz.meta["requires_ram"] == ram

            # invalid required RAM (must be one of enumerated values)
            with pytest.raises(wozardry.WozMETAFormatError_BadRAM):
                wozardry.parse_args(["edit", "-m", "requires_ram:65K", tmp.name])

    f(kValid1)
    f(kValid2)

def test_command_edit_requires_machine():
    """edit a WOZ1/WOZ2 file to change the metadata requires_machine field"""
    def f(inputfile):
        with tempfile.NamedTemporaryFile() as tmp:
            shutil.copy(inputfile, tmp.name)

            for model in wozardry.kRequiresMachine:
                wozardry.parse_args(["edit", "-m", "requires_machine:%s" % model, tmp.name])
                with open(tmp.name, "rb") as tmpstream:
                    woz = wozardry.WozDiskImage(tmpstream)
                assert woz.meta["requires_machine"] == model

            # invalid machine (Apple IV)
            with pytest.raises(wozardry.WozMETAFormatError_BadMachine):
                wozardry.parse_args(["edit", "-m", "requires_machine:4", tmp.name])

    f(kValid1)
    f(kValid2)
