#!/usr/bin/env python3

# (c) 2018-9 by 4am
# MIT-licensed

import argparse
import binascii
import bitarray # https://pypi.org/project/bitarray/
import collections
import io
import json
import itertools
import os
import sys

__version__ = "2.0.1" # https://semver.org
__date__ = "2020-10-02"
__progname__ = "wozardry"
__displayname__ = __progname__ + " " + __version__ + " by 4am (" + __date__ + ")"

# domain-specific constants defined in .woz specifications
kWOZ1 = b"WOZ1"
kWOZ2 = b"WOZ2"
kINFO = b"INFO"
kTMAP = b"TMAP"
kTRKS = b"TRKS"
kWRIT = b"WRIT" # WOZ2 only
kMETA = b"META"
kBitstreamLengthInBytes = 6646 # WOZ1 only
kLanguages = ("English","Spanish","French","German","Chinese","Japanese","Italian","Dutch","Portuguese","Danish","Finnish","Norwegian","Swedish","Russian","Polish","Turkish","Arabic","Thai","Czech","Hungarian","Catalan","Croatian","Greek","Hebrew","Romanian","Slovak","Ukrainian","Indonesian","Malay","Vietnamese","Other")
kRequiresRAM = ("16K","24K","32K","48K","64K","128K","256K","512K","768K","1M","1.25M","1.5M+","Unknown")
kRequiresMachine = ("2","2+","2e","2c","2e+","2gs","2c+","3","3+")
kDefaultBitTiming = (0, 32, 16) # WOZ2 only

# strings and things, for print routines and error messages
sEOF = "Unexpected EOF"
sBadChunkSize = "Bad chunk size"
dNoYes = {False:"no",True:"yes"}
tQuarters = (".00",".25",".50",".75")
tDiskType = {(1,1,False): "5.25-inch (140K)",
             (2,1,False): "3.5-inch (400K)",
             (2,2,False): "3.5-inch (800K)",
             (2,2,True):  "3.5-inch (1.44MB)"}
tBootSectorFormat = ("unknown", "16-sector", "13-sector", "hybrid 13- and 16-sector")
tDefaultCreator = (__progname__ + " " + __version__)[:32]

# errors that may be raised
class WozError(Exception): pass # base class
class WozCRCError(WozError): pass
class WozFormatError(WozError): pass
class WozEOFError(WozFormatError): pass
class WozHeaderError(WozFormatError): pass
class WozHeaderError_NoWOZMarker(WozHeaderError): pass
class WozHeaderError_NoFF(WozHeaderError): pass
class WozHeaderError_NoLF(WozHeaderError): pass
class WozINFOFormatError(WozFormatError): pass
class WozINFOFormatError_MissingINFOChunk(WozINFOFormatError): pass
class WozINFOFormatError_BadVersion(WozINFOFormatError): pass
class WozINFOFormatError_BadDiskType(WozINFOFormatError): pass
class WozINFOFormatError_BadWriteProtected(WozINFOFormatError): pass
class WozINFOFormatError_BadSynchronized(WozINFOFormatError): pass
class WozINFOFormatError_BadCleaned(WozINFOFormatError): pass
class WozINFOFormatError_BadCreator(WozINFOFormatError): pass
class WozINFOFormatError_BadDiskSides(WozINFOFormatError): pass
class WozINFOFormatError_BadBootSectorFormat(WozINFOFormatError): pass
class WozINFOFormatError_BadOptimalBitTiming(WozINFOFormatError): pass
class WozINFOFormatError_BadCompatibleHardware(WozINFOFormatError): pass
class WozTMAPFormatError(WozFormatError): pass
class WozTMAPFormatError_MissingTMAPChunk(WozTMAPFormatError): pass
class WozTMAPFormatError_BadTRKS(WozTMAPFormatError): pass
class WozTRKSFormatError(WozFormatError): pass
class WozTRKSFormatError_BadStartingBlock(WozTRKSFormatError): pass
class WozTRKSFormatError_BadBlockCount(WozTRKSFormatError): pass
class WozTRKSFormatError_BadBitCount(WozTRKSFormatError): pass
class WozMETAFormatError(WozFormatError): pass
class WozMETAFormatError_EncodingError(WozFormatError): pass
class WozMETAFormatError_NotEnoughTabs(WozFormatError): pass
class WozMETAFormatError_TooManyTabs(WozFormatError): pass
class WozMETAFormatError_DuplicateKey(WozFormatError): pass
class WozMETAFormatError_BadValue(WozFormatError): pass
class WozMETAFormatError_BadLanguage(WozFormatError): pass
class WozMETAFormatError_BadRAM(WozFormatError): pass
class WozMETAFormatError_BadMachine(WozFormatError): pass

def from_uint32(b):
    return int.from_bytes(b, byteorder="little")
from_uint16=from_uint32
from_uint8=from_uint32

def to_uint32(b):
    return b.to_bytes(4, byteorder="little")

def to_uint16(b):
    return b.to_bytes(2, byteorder="little")

def to_uint8(b):
    return b.to_bytes(1, byteorder="little")

def is_booleanish(v):
    if type(v) is str:
        try:
            return is_booleanish(int(v))
        except:
            return v.lower() in ("true","false","yes","no","1","0")
    elif type(v) is bytes:
        try:
            return is_booleanish(int.from_bytes(v, byteorder="little"))
        except:
            return False
    return v in (0, 1)

def from_booleanish(v, errorClass, errorString):
    raise_if(not is_booleanish(v), errorClass, errorString % v)
    if type(v) is str:
        return v.lower() in ("true","yes","1")
    elif type(v) is bytes:
        return v == b"\x01"
    return v == 1

def is_intish(v):
    if type(v) is str:
        try:
            int(v)
            return True
        except:
            return False
    if type(v) is bytes:
        try:
            int.from_bytes(v, byteorder="little")
            return True
        except:
            return False
    return type(v) is int

def from_intish(v, errorClass, errorString):
    raise_if(not is_intish(v), errorClass, errorString % v)
    if type(v) is str:
        return int(v)
    elif type(v) is bytes:
        return int.from_bytes(v, byteorder="little")
    return v

def raise_if(cond, e, s=""):
    if cond: raise e(s)

class Track:
    def __init__(self, bits, bit_count):
        self.bits = bits
        while len(self.bits) > bit_count:
            self.bits.pop()
        self.bit_count = bit_count
        self.bit_index = 0
        self.revolutions = 0

    def bit(self):
        b = self.bits[self.bit_index] and 1 or 0
        self.bit_index += 1
        if self.bit_index >= self.bit_count:
            self.bit_index = 0
            self.revolutions += 1
        yield b

    def nibble(self):
        b = 0
        while b == 0:
            b = next(self.bit())
        n = 0x80
        for bit_index in range(6, -1, -1):
            b = next(self.bit())
            n += b << bit_index
        yield n

    def rewind(self, bit_count):
        self.bit_index -= 1
        if self.bit_index < 0:
            self.bit_index = self.bit_count - 1
            self.revolutions -= 1

    def find(self, sequence):
        starting_revolutions = self.revolutions
        seen = [0] * len(sequence)
        while (self.revolutions < starting_revolutions + 2):
            del seen[0]
            seen.append(next(self.nibble()))
            if tuple(seen) == tuple(sequence): return True
        return False

class WozDiskImage:
    def __init__(self, iostream=None):
        if iostream:
            self.load(iostream)
        else:
            self.reset()

    def reset(self):
        self.info = collections.OrderedDict()
        self.tmap = [0xFF]*160
        self.tracks = []
        self.writ = None
        self.meta = collections.OrderedDict()
        self.woz_version = 2
        self.info["version"] = self.woz_version
        self.info["disk_type"] = 1
        self.info["write_protected"] = False
        self.info["synchronized"] = False
        self.info["cleaned"] = False
        self.info["creator"] = tDefaultCreator
        self.info["disk_sides"] = 1
        self.info["boot_sector_format"] = 0
        self.info["optimal_bit_timing"] = 32
        self.info["compatible_hardware"] = []
        self.info["required_ram"] = 0

    def load(self, iostream):
        self.reset()
        seen_info = False
        seen_tmap = False
        header_raw = iostream.read(8)
        raise_if(len(header_raw) != 8, WozEOFError, sEOF)
        self._load_header(header_raw)
        crc_raw = iostream.read(4)
        raise_if(len(crc_raw) != 4, WozEOFError, sEOF)
        crc = from_uint32(crc_raw)
        all_data = []
        while True:
            chunk_id = iostream.read(4)
            if not chunk_id: break
            raise_if(len(chunk_id) != 4, WozEOFError, sEOF)
            all_data.append(chunk_id)
            chunk_size_raw = iostream.read(4)
            raise_if(len(chunk_size_raw) != 4, WozEOFError, sEOF)
            all_data.append(chunk_size_raw)
            chunk_size = from_uint32(chunk_size_raw)
            data = iostream.read(chunk_size)
            raise_if(len(data) != chunk_size, WozEOFError, sEOF)
            all_data.append(data)
            if chunk_id == kINFO:
                raise_if(chunk_size != 60, WozINFOFormatError, sBadChunkSize)
                self._load_info(data)
                seen_info = True
                continue
            raise_if(not seen_info, WozINFOFormatError_MissingINFOChunk, "Expected INFO chunk at offset 20")
            if chunk_id == kTMAP:
                raise_if(chunk_size != 160, WozTMAPFormatError, sBadChunkSize)
                self._load_tmap(data)
                seen_tmap = True
                continue
            raise_if(not seen_tmap, WozTMAPFormatError_MissingTMAPChunk, "Expected TMAP chunk at offset 88")
            if chunk_id == kTRKS:
                self._load_trks(data)
            elif chunk_id == kWRIT:
                self._load_writ(data)
            elif chunk_id == kMETA:
                self._load_meta(data)
        raise_if(not seen_info, WozINFOFormatError_MissingINFOChunk, "Expected INFO chunk at offset 20")
        raise_if(not seen_tmap, WozTMAPFormatError_MissingTMAPChunk, "Expected TMAP chunk at offset 88")
        if crc:
            raise_if(crc != binascii.crc32(b"".join(all_data)) & 0xffffffff, WozCRCError, "Bad CRC")

    def _load_header(self, data):
        raise_if(data[:4] not in (kWOZ1, kWOZ2), WozHeaderError_NoWOZMarker, "Magic string 'WOZ1' or 'WOZ2' not present at offset 0")
        self.woz_version = int(data[3]) - 0x30
        raise_if(data[4] != 0xFF, WozHeaderError_NoFF, "Magic byte 0xFF not present at offset 4")
        raise_if(data[5:8] != b"\x0A\x0D\x0A", WozHeaderError_NoLF, "Magic bytes 0x0A0D0A not present at offset 5")

    def _load_info(self, data):
        self.info["version"] = self.validate_info_version(data[0]) # int
        self.info["disk_type"] = self.validate_info_disk_type(data[1]) # int
        self.info["write_protected"] = self.validate_info_write_protected(data[2]) # boolean
        self.info["synchronized"] = self.validate_info_synchronized(data[3]) # boolean
        self.info["cleaned"] = self.validate_info_cleaned(data[4]) # boolean
        self.info["creator"] = self.validate_info_creator(data[5:37]) # string
        if self.info["version"] >= 2:
            self.info["disk_sides"] = self.validate_info_disk_sides(data[37]) # int
            self.info["boot_sector_format"] = self.validate_info_boot_sector_format(data[38]) # int
            self.info["optimal_bit_timing"] = self.validate_info_optimal_bit_timing(data[39]) # int
            compatible_hardware_bitfield = self.validate_info_compatible_hardware(data[40:42]) # int
            compatible_hardware_list = []
            for offset in range(9):
                if compatible_hardware_bitfield & (1 << offset):
                    compatible_hardware_list.append(kRequiresMachine[offset])
            self.info["compatible_hardware"] = compatible_hardware_list
            self.info["required_ram"] = self.validate_info_required_ram(data[42:44])
            self.info["largest_track"] = from_uint16(data[44:46])

    def _load_tmap(self, data):
        self.tmap = list(data)

    def _load_trks(self, data):
        if self.info["version"] == 1:
            self._load_trks_v1(data)
        else:
            self._load_trks_v2(data)
        for trk, i in zip(self.tmap, itertools.count()):
            raise_if(trk != 0xFF and trk >= len(self.tracks), WozTMAPFormatError_BadTRKS, "Invalid TMAP entry: track %d%s points to non-existent TRKS chunk %d" % (i/4, tQuarters[i%4], trk))

    def _load_trks_v1(self, data):
        i = 0
        while i < len(data):
            raw_bytes = data[i:i+kBitstreamLengthInBytes]
            raise_if(len(raw_bytes) != kBitstreamLengthInBytes, WozEOFError, sEOF)
            i += kBitstreamLengthInBytes
            bytes_used_raw = data[i:i+2]
            raise_if(len(bytes_used_raw) != 2, WozEOFError, sEOF)
            bytes_used = from_uint16(bytes_used_raw)
            raise_if(bytes_used > kBitstreamLengthInBytes, WozTRKSFormatError, "TRKS chunk %d bytes_used is out of range" % len(self.tracks))
            i += 2
            bit_count_raw = data[i:i+2]
            raise_if(len(bit_count_raw) != 2, WozEOFError, sEOF)
            bit_count = from_uint16(bit_count_raw)
            i += 2
            splice_point_raw = data[i:i+2]
            raise_if(len(splice_point_raw) != 2, WozEOFError, sEOF)
            splice_point = from_uint16(splice_point_raw)
            if splice_point != 0xFFFF:
                raise_if(splice_point > bit_count, WozTRKSFormatError, "TRKS chunk %d splice_point is out of range" % len(self.tracks))
            i += 2
            splice_nibble = data[i]
            i += 1
            splice_bit_count = data[i]
            if splice_point != 0xFFFF:
                raise_if(splice_bit_count not in (8,9,10), WozTRKSFormatError, "TRKS chunk %d splice_bit_count is out of range" % len(self.tracks))
            i += 3
            bits = bitarray.bitarray(endian="big")
            bits.frombytes(raw_bytes)
            self.tracks.append(Track(bits, bit_count))

    def _load_trks_v2(self, data):
        for trk in range(160):
            i = trk * 8
            starting_block = from_uint16(data[i:i+2])
            raise_if(starting_block in (1,2), WozTRKSFormatError_BadStartingBlock, "TRKS TRK %d starting_block out of range (expected 3+ or 0, found %s)" % (trk, starting_block))
            block_count = from_uint16(data[i+2:i+4])
            bit_count = from_uint32(data[i+4:i+8])
            if starting_block == 0:
                raise_if(block_count != 0, WozTRKSFormatError_BadBlockCount, "TRKS unused TRK %d block_count must be 0 (found %s)" % (trk, block_count))
                raise_if(bit_count != 0, WozTRKSFormatError_BadBitCount, "TRKS unused TRK %d bit_count must be 0 (found %s)" % (trk, bit_count))
                break
            bits_index_into_data = 1280 + (starting_block-3)*512
            raise_if(len(data) <= bits_index_into_data, WozTRKSFormatError_BadStartingBlock, sEOF)
            raw_bytes = data[bits_index_into_data : bits_index_into_data + block_count*512]
            raise_if(len(raw_bytes) != block_count*512, WozTRKSFormatError_BadBlockCount, sEOF)
            bits = bitarray.bitarray(endian="big")
            bits.frombytes(raw_bytes)
            self.tracks.append(Track(bits, bit_count))

    def _load_writ(self, data):
        self.writ = data

    def _load_meta(self, metadata_as_bytes):
        metadata = self.decode_metadata(metadata_as_bytes)
        for line in metadata.split("\n"):
            if not line: continue
            columns_raw = line.split("\t")
            raise_if(len(columns_raw) < 2, WozMETAFormatError_NotEnoughTabs, "Malformed metadata")
            raise_if(len(columns_raw) > 2, WozMETAFormatError_TooManyTabs, "Malformed metadata")
            key, value_raw = columns_raw
            raise_if(key in self.meta, WozMETAFormatError_DuplicateKey, "Duplicate metadata key %s" % key)
            values = value_raw.split("|")
            if key == "language":
                list(map(self.validate_metadata_language, values))
            elif key == "requires_ram":
                list(map(self.validate_metadata_requires_ram, values))
            elif key == "requires_machine":
                list(map(self.validate_metadata_requires_machine, values))
            self.meta[key] = len(values) == 1 and values[0] or tuple(values)

    def validate_info_version(self, version):
        """ |version| can be str, bytes, or int. returns same value as int"""
        version = from_intish(version, WozINFOFormatError_BadVersion, "Unknown version (expected numeric value, found %s)")
        if self.woz_version == 1:
            raise_if(version != 1, WozINFOFormatError_BadVersion, "Unknown version (expected 1, found %s)" % version)
        else:
            raise_if(version < 2, WozINFOFormatError_BadVersion, "Unknown version (expected 2 or more, found %s)" % version)
        return version

    def validate_info_disk_type(self, disk_type):
        """ |disk_type| can be str, bytes, or int. returns same value as int"""
        disk_type = from_intish(disk_type, WozINFOFormatError_BadDiskType, "Unknown disk type (expected numeric value, found %s)")
        raise_if(disk_type not in (1, 2), WozINFOFormatError_BadDiskType, "Unknown disk type (expected 1 or 2, found %s)" % disk_type)
        return disk_type

    def validate_info_write_protected(self, write_protected):
        """|write_protected| can be str, bytes, or int. returns same value as bool"""
        return from_booleanish(write_protected, WozINFOFormatError_BadWriteProtected, "Unknown write protected flag (expected Boolean value, found %s)")

    def validate_info_synchronized(self, synchronized):
        """|synchronized| can be str, bytes, or int. returns same value as bool"""
        return from_booleanish(synchronized, WozINFOFormatError_BadSynchronized, "Unknown synchronized flag (expected Boolean value, found %s)")

    def validate_info_cleaned(self, cleaned):
        """|cleaned| can be str, bytes, or int. returns same value as bool"""
        return from_booleanish(cleaned, WozINFOFormatError_BadCleaned, "Unknown cleaned flag (expected Boolean value, found %s)")

    def validate_info_creator(self, creator_as_bytes):
        raise_if(len(creator_as_bytes) > 32, WozINFOFormatError_BadCreator, "Creator is longer than 32 bytes")
        try:
            return creator_as_bytes.decode("UTF-8").strip()
        except:
            raise_if(True, WozINFOFormatError_BadCreator, "Creator is not valid UTF-8")

    def encode_info_creator(self, creator_as_string):
        creator_as_bytes = creator_as_string.encode("UTF-8").ljust(32, b" ")
        self.validate_info_creator(creator_as_bytes)
        return creator_as_bytes

    def validate_info_disk_sides(self, disk_sides):
        """|disk_sides| can be str, bytes, or int. returns same value as int"""
        # assumes WOZ version 2 or later
        disk_sides = from_intish(disk_sides, WozINFOFormatError_BadDiskSides, "Bad disk sides (expected numeric value, found %s)")
        if self.info["disk_type"] == 1: # 5.25-inch disk
            raise_if(disk_sides != 1, WozINFOFormatError_BadDiskSides, "Bad disk sides (expected 1 for a 5.25-inch disk, found %s)")
        elif self.info["disk_type"] == 2: # 3.5-inch disk
            raise_if(disk_sides not in (1, 2), WozINFOFormatError_BadDiskSides, "Bad disk sides (expected 1 or 2 for a 3.5-inch disk, found %s)" % disk_sides)
        return disk_sides

    def validate_info_boot_sector_format(self, boot_sector_format):
        """|boot_sector_format| can be str, bytes, or int. returns same value as int"""
        # assumes WOZ version 2 or later
        boot_sector_format = from_intish(boot_sector_format, WozINFOFormatError_BadBootSectorFormat, "Bad boot sector format (expected numeric value, found %s)")
        if self.info["disk_type"] == 1: # 5.25-inch disk
            raise_if(boot_sector_format not in (0,1,2,3), WozINFOFormatError_BadBootSectorFormat, "Bad boot sector format (expected 0,1,2,3 for a 5.25-inch disk, found %s)" % boot_sector_format)
        elif self.info["disk_type"] == 2: # 3.5-inch disk
            raise_if(boot_sector_format != 0, WozINFOFormatError_BadBootSectorFormat, "Bad boot sector format (expected 0 for a 3.5-inch disk, found %s)" % boot_sector_format)
        return boot_sector_format

    def validate_info_optimal_bit_timing(self, optimal_bit_timing):
        """|optimal_bit_timing| can be str, bytes, or int. returns same value as int"""
        # assumes WOZ version 2 or later
        optimal_bit_timing = from_intish(optimal_bit_timing, WozINFOFormatError_BadOptimalBitTiming, "Bad optimal bit timing (expected numeric value, found %s)")
        if self.info["disk_type"] == 1: # 5.25-inch disk
            raise_if(optimal_bit_timing not in range(24, 41), WozINFOFormatError_BadOptimalBitTiming, "Bad optimal bit timing (expected 24-40 for a 5.25-inch disk, found %s)" % optimal_bit_timing)
        elif self.info["disk_type"] == 2: # 3.5-inch disk
            raise_if(optimal_bit_timing not in range(8, 25), WozINFOFormatError_BadOptimalBitTiming, "Bad optimal bit timing (expected 8-24 for a 3.5-inch disk, found %s)" % optimal_bit_timing)
        return optimal_bit_timing

    def validate_info_compatible_hardware(self, compatible_hardware):
        """|compatible_hardware| is bytes, returns same value as int"""
        # assumes WOZ version 2 or later
        compatible_hardware = from_uint16(compatible_hardware)
        raise_if(compatible_hardware >= 0x01FF, WozINFOFormatError_BadCompatibleHardware, "Bad compatible hardware (7 high bits must be 0 but some were 1)")
        return compatible_hardware

    def validate_info_required_ram(self, required_ram):
        """|required_ram| can be str, bytes, or int. returns same value as int"""
        # assumes WOZ version 2 or later
        required_ram = from_intish(required_ram, WozINFOFormatError_BadOptimalBitTiming, "Bad required RAM (expected numeric value, found %s)")
        return required_ram

    def validate_metadata(self, metadata_as_bytes):
        try:
            metadata = metadata_as_bytes.decode("UTF-8")
        except:
            raise WozMETAFormatError_EncodingError("Metadata is not valid UTF-8")

    def decode_metadata(self, metadata_as_bytes):
        self.validate_metadata(metadata_as_bytes)
        return metadata_as_bytes.decode("UTF-8")

    def validate_metadata_value(self, value):
        raise_if("\t" in value, WozMETAFormatError_BadValue, "Invalid metadata value (contains tab character)")
        raise_if("\n" in value, WozMETAFormatError_BadValue, "Invalid metadata value (contains linefeed character)")
        raise_if("|" in value, WozMETAFormatError_BadValue, "Invalid metadata value (contains pipe character)")

    def validate_metadata_language(self, language):
        raise_if(language and (language not in kLanguages), WozMETAFormatError_BadLanguage, "Invalid metadata language")

    def validate_metadata_requires_ram(self, requires_ram):
        raise_if(requires_ram and (requires_ram not in kRequiresRAM), WozMETAFormatError_BadRAM, "Invalid metadata requires_ram")

    def validate_metadata_requires_machine(self, requires_machine):
        raise_if(requires_machine and (requires_machine not in kRequiresMachine), WozMETAFormatError_BadMachine, "Invalid metadata requires_machine")

    def __bytes__(self):
        return self.dump()

    def dump(self):
        """returns serialization of the disk image in bytes, suitable for writing to disk"""
        info = self._dump_info()
        tmap = self._dump_tmap()
        trks = self._dump_trks()
        writ = self._dump_writ() # will be zero-length if no WRIT chunk
        meta = self._dump_meta() # will be zero-length if no META chunk
        crc = binascii.crc32(info + tmap + trks + writ + meta)
        head = self._dump_head(crc)
        return bytes(head + info + tmap + trks + writ + meta)

    def _dump_info(self):
        chunk = bytearray()
        chunk.extend(kINFO) # chunk ID
        chunk.extend(to_uint32(60)) # chunk size (constant)
        version_raw = to_uint8(self.info["version"])
        self.validate_info_version(version_raw)
        disk_type_raw = to_uint8(self.info["disk_type"])
        self.validate_info_disk_type(disk_type_raw)
        write_protected_raw = to_uint8(self.info["write_protected"])
        self.validate_info_write_protected(write_protected_raw)
        synchronized_raw = to_uint8(self.info["synchronized"])
        self.validate_info_synchronized(synchronized_raw)
        cleaned_raw = to_uint8(self.info["cleaned"])
        self.validate_info_cleaned(cleaned_raw)
        creator_raw = self.encode_info_creator(self.info["creator"])
        chunk.extend(version_raw) # 1 byte, 1 or 2
        chunk.extend(disk_type_raw) # 1 byte, 1=5.25 inch, 2=3.5 inch
        chunk.extend(write_protected_raw) # 1 byte, 0=no, 1=yes
        chunk.extend(synchronized_raw) # 1 byte, 0=no, 1=yes
        chunk.extend(cleaned_raw) # 1 byte, 0=no, 1=yes
        chunk.extend(creator_raw) # 32 bytes, UTF-8 encoded string
        if self.woz_version == 1:
            chunk.extend(b"\x00" * 23) # 23 bytes of unused space
        else:
            disk_sides_raw = to_uint8(self.info["disk_sides"])
            self.validate_info_disk_sides(disk_sides_raw)
            boot_sector_format_raw = to_uint8(self.info["boot_sector_format"])
            self.validate_info_boot_sector_format(boot_sector_format_raw)
            optimal_bit_timing_raw = to_uint8(self.info["optimal_bit_timing"])
            self.validate_info_optimal_bit_timing(optimal_bit_timing_raw)
            compatible_hardware_bitfield = 0
            for offset in range(9):
                if kRequiresMachine[offset] in self.info["compatible_hardware"]:
                    compatible_hardware_bitfield |= (1 << offset)
            compatible_hardware_raw = to_uint16(compatible_hardware_bitfield)
            required_ram_raw = to_uint16(self.info["required_ram"])
            if self.tracks:
                largest_bit_count = max([track.bit_count for track in self.tracks])
                largest_block_count = (((largest_bit_count+7)//8)+511)//512
            else:
                largest_block_count = 0
            largest_track_raw = to_uint16(largest_block_count)
            chunk.extend(disk_sides_raw) # 1 byte, 1 or 2
            chunk.extend(boot_sector_format_raw) # 1 byte, 0,1,2,3
            chunk.extend(optimal_bit_timing_raw) # 1 byte
            chunk.extend(compatible_hardware_raw) # 2 bytes, bitfield
            chunk.extend(required_ram_raw) # 2 bytes
            chunk.extend(largest_track_raw) # 2 bytes
            chunk.extend(b"\x00" * 14) # 14 bytes of unused space
        return chunk

    def _dump_tmap(self):
        chunk = bytearray()
        chunk.extend(kTMAP) # chunk ID
        chunk.extend(to_uint32(160)) # chunk size
        chunk.extend(bytes(self.tmap))
        return chunk

    def _dump_trks(self):
        if self.woz_version == 1:
            return self._dump_trks_v1()
        else:
            return self._dump_trks_v2()

    def _dump_trks_v1(self):
        chunk = bytearray()
        chunk.extend(kTRKS) # chunk ID
        chunk_size = len(self.tracks)*6656
        chunk.extend(to_uint32(chunk_size)) # chunk size
        for track in self.tracks:
            raw_bytes = track.bits.tobytes()
            chunk.extend(raw_bytes) # bitstream as raw bytes
            chunk.extend(b"\x00" * (6646 - len(raw_bytes))) # padding to 6646 bytes
            chunk.extend(to_uint16(len(raw_bytes))) # bytes used
            chunk.extend(to_uint16(track.bit_count)) # bit count
            chunk.extend(b"\xFF\xFF") # splice point (none)
            chunk.extend(b"\xFF") # splice nibble (none)
            chunk.extend(b"\xFF") # splice bit count (none)
            chunk.extend(b"\x00\x00") # reserved
        return chunk

    def _dump_trks_v2(self):
        starting_block = 3
        trk_chunk = bytearray()
        bits_chunk = bytearray()
        for track in self.tracks:
            # get bitstream as bytes and pad to multiple of 512
            padded_bytes = track.bits.tobytes()
            padded_bytes += (512 - (len(padded_bytes) % 512))*b"\x00"
            trk_chunk.extend(to_uint16(starting_block))
            block_size = len(padded_bytes) // 512
            starting_block += block_size
            trk_chunk.extend(to_uint16(block_size))
            trk_chunk.extend(to_uint32(len(track.bits)))
            bits_chunk.extend(padded_bytes)
        for i in range(len(self.tracks), 160):
            trk_chunk.extend(to_uint16(0))
            trk_chunk.extend(to_uint16(0))
            trk_chunk.extend(to_uint32(0))
        chunk = bytearray()
        chunk.extend(kTRKS) # chunk ID
        chunk.extend(to_uint32(len(trk_chunk) + len(bits_chunk)))
        chunk.extend(trk_chunk)
        chunk.extend(bits_chunk)
        return chunk

    def _dump_writ(self):
        chunk = bytearray()
        if self.writ:
            chunk.extend(kWRIT) # chunk ID
            chunk.extend(to_uint32(len(self.writ))) # chunk size
            chunk.extend(self.writ)
        return chunk

    def _dump_meta(self):
        if not self.meta: return b""
        meta_tmp = {}
        for key, value_raw in self.meta.items():
            if type(value_raw) == str:
                values = [value_raw]
            else:
                values = value_raw
            meta_tmp[key] = values
            list(map(self.validate_metadata_value, values))
            if key == "language":
                list(map(self.validate_metadata_language, values))
            elif key == "requires_ram":
                list(map(self.validate_metadata_requires_ram, values))
            elif key == "requires_machine":
                list(map(self.validate_metadata_requires_machine, values))
        data = b"\x0A".join(
            [k.encode("UTF-8") + \
             b"\x09" + \
             "|".join(v).encode("UTF-8") \
             for k, v in meta_tmp.items()]) + b'\x0A'
        chunk = bytearray()
        chunk.extend(kMETA) # chunk ID
        chunk.extend(to_uint32(len(data))) # chunk size
        chunk.extend(data)
        return chunk

    def _dump_head(self, crc):
        chunk = bytearray()
        if self.woz_version == 1:
            chunk.extend(kWOZ1) # magic bytes
        else:
            chunk.extend(kWOZ2) # magic bytes
        chunk.extend(b"\xFF\x0A\x0D\x0A") # more magic bytes
        chunk.extend(to_uint32(crc)) # CRC32 of rest of file (calculated in caller)
        return chunk

    def track_num_to_half_phase(self, track_num):
        if type(track_num) != float:
            track_num = float(track_num)
        if track_num < 0.0 or \
           track_num > 40.0 or \
           track_num.as_integer_ratio()[1] not in (1,2,4):
            raise WozError("Invalid track %s" % track_num)
        return int(track_num * 4)

    def add(self, half_phase, track):
        trk_id = len(self.tracks)
        self.tracks.append(track)
        self.tmap[half_phase] = trk_id
        if half_phase:
            self.tmap[half_phase - 1] = trk_id
        if half_phase < 159:
            self.tmap[half_phase + 1] = trk_id

    def add_track(self, track_num, track):
        self.add(self.track_num_to_half_phase(track_num), track)

    def remove(self, half_phase):
        if self.tmap[half_phase] == 0xFF: return False
        self.tmap[half_phase] = 0xFF
        self.clean()
        return True

    def remove_track(self, track_num):
        """removes given track, returns True if anything was actually removed, or False if track wasn't found. track_num can be 0..40 in 0.25 increments (0, 0.25, 0.5, 0.75, 1, &c.)"""
        return self.remove(self.track_num_to_half_phase(track_num))

    def clean(self):
        """removes tracks from self.tracks that are not referenced from self.tmap, and adjusts remaining self.tmap indices"""
        i = 0
        while i < len(self.tracks):
            if i not in self.tmap:
                del self.tracks[i]
                for adjust in range(len(self.tmap)):
                    if (self.tmap[adjust] >= i) and (self.tmap[adjust] != 0xFF):
                        self.tmap[adjust] -= 1
            else:
                i += 1

    def seek(self, track_num):
        """returns Track object for the given track, or None if the track is not part of this disk image. track_num can be 0..40 in 0.25 increments (0, 0.25, 0.5, 0.75, 1, &c.)"""
        half_phase = self.track_num_to_half_phase(track_num)
        trk_id = self.tmap[half_phase]
        if trk_id == 0xFF: return None
        return self.tracks[trk_id]

    def from_json(self, json_string):
        j = json.loads(json_string)
        root = [x for x in j.keys()].pop()
        self.meta.update(j[root]["meta"])

    def to_json(self):
        j = {"woz": {"info":self.info, "meta":self.meta}}
        return json.dumps(j, indent=2)

#---------- command line interface ----------

class _BaseCommand:
    def __init__(self, name):
        self.name = name

    def setup(self, subparser, description=None, epilog=None, help=".woz disk image", formatter_class=argparse.HelpFormatter):
        self.parser = subparser.add_parser(self.name, description=description, epilog=epilog, formatter_class=formatter_class)
        self.parser.add_argument("file", help=help)
        self.parser.set_defaults(action=self)

    def __call__(self, args):
        with open(args.file, "rb") as f:
            self.woz_image = WozDiskImage(f)

class _CommandVerify(_BaseCommand):
    def __init__(self):
        _BaseCommand.__init__(self, "verify")

    def setup(self, subparser):
        _BaseCommand.setup(self, subparser,
                          description="Verify file structure and metadata of a .woz disk image (produces no output unless a problem is found)")

class _CommandDump(_BaseCommand):
    kWidth = 30

    def __init__(self):
        _BaseCommand.__init__(self, "dump")

    def setup(self, subparser):
        _BaseCommand.setup(self, subparser,
                          description="Print all available information and metadata in a .woz disk image")

    def __call__(self, args):
        _BaseCommand.__call__(self, args)
        self.print_tmap()
        self.print_meta()
        self.print_info()

    def print_info(self):
        info = self.woz_image.info
        info_version = info["version"]
        print("INFO:  File format version:".ljust(self.kWidth), "%d" % info_version)
        disk_type = info["disk_type"]
        disk_sides = info_version >= 2 and info["disk_sides"] or 1
        large_disk = disk_sides == 2 and info["largest_track"] >= 0x20
        print("INFO:  Disk type:".ljust(self.kWidth),           tDiskType[(disk_type,disk_sides,large_disk)])
        print("INFO:  Write protected:".ljust(self.kWidth),     dNoYes[info["write_protected"]])
        print("INFO:  Tracks synchronized:".ljust(self.kWidth),  dNoYes[info["synchronized"]])
        print("INFO:  Weakbits cleaned:".ljust(self.kWidth),    dNoYes[info["cleaned"]])
        print("INFO:  Creator:".ljust(self.kWidth),             info["creator"])
        if info_version == 1: return
        if disk_type == 1: # 5.25-inch disk
            boot_sector_format = info["boot_sector_format"]
            print("INFO:  Boot sector format:".ljust(self.kWidth), "%s (%s)" % (boot_sector_format, tBootSectorFormat[boot_sector_format]))
        else: # 3.5-inch disk
            print("INFO:  Disk sides:".ljust(self.kWidth), disk_sides)
        default_bit_timing = kDefaultBitTiming[disk_type]
        optimal_bit_timing = info["optimal_bit_timing"]
        print("INFO:  Optimal bit timing:".ljust(self.kWidth), optimal_bit_timing,
              optimal_bit_timing == default_bit_timing and "(standard)" or
              optimal_bit_timing < default_bit_timing and "(fast)" or "(slow)")
        compatible_hardware_list = info["compatible_hardware"]
        if not compatible_hardware_list:
            print("INFO:  Compatible hardware:".ljust(self.kWidth), "unknown")
        else:
            print("INFO:  Compatible hardware:".ljust(self.kWidth), compatible_hardware_list[0])
            for value in compatible_hardware_list[1:]:
                print("INFO:  ".ljust(self.kWidth), value)
        ram = info["required_ram"]
        print("INFO:  Required RAM:".ljust(self.kWidth), ram and "%sK" % ram or "unknown")
        print("INFO:  Largest track:".ljust(self.kWidth), info["largest_track"], "blocks")

    def print_tmap(self):
        if self.woz_image.info["disk_type"] == 1:
            self.print_tmap_525()
        else:
            self.print_tmap_35()

    def print_tmap_525(self):
        i = 0
        for trk, i in zip(self.woz_image.tmap, itertools.count()):
            if trk != 0xFF:
                print(("TMAP:  Track %d%s" % (i/4, tQuarters[i%4])).ljust(self.kWidth), "TRKS %d" % (trk))

    def print_tmap_35(self):
        track_num = 0
        side_num = 0
        for trk in self.woz_image.tmap:
            if trk != 0xFF:
                print(("TMAP:  Track %d, Side %d" % (track_num, side_num)).ljust(self.kWidth), "TRKS %d" % (trk))
            side_num = 1 - side_num
            if not side_num:
                track_num += 1

    def print_meta(self):
        if not self.woz_image.meta: return
        for key, values in self.woz_image.meta.items():
            if type(values) == str:
                values = [values]
            print(("META:  " + key + ":").ljust(self.kWidth), values[0])
            for value in values[1:]:
                print("META:  ".ljust(self.kWidth), value)

class _CommandExport(_BaseCommand):
    def __init__(self):
        _BaseCommand.__init__(self, "export")

    def setup(self, subparser):
        _BaseCommand.setup(self, subparser,
                          description="Export (as JSON) all information and metadata from a .woz disk image")

    def __call__(self, args):
        _BaseCommand.__call__(self, args)
        print(self.woz_image.to_json())

class _WriterBaseCommand(_BaseCommand):
    def __call__(self, args):
        _BaseCommand.__call__(self, args)
        self.update(args)
        output_as_bytes = bytes(self.woz_image)
        # as a final sanity check, load and parse the output we just created
        # to help ensure we never create invalid .woz files
        try:
            global raise_if
            raise_if = old_raise_if
        except:
            pass
        try:
            WozDiskImage(io.BytesIO(output_as_bytes))
        except Exception as e:
            sys.stderr.write("WozInternalError: refusing to write an invalid .woz file (this is the developer's fault)\n")
            raise Exception from e
        tmpfile = args.file + ".ardry"
        with open(tmpfile, "wb") as tmp:
            tmp.write(output_as_bytes)
        os.rename(tmpfile, args.file)

class _CommandEdit(_WriterBaseCommand):
    def __init__(self):
        _WriterBaseCommand.__init__(self, "edit")

    def setup(self, subparser):
        _WriterBaseCommand.setup(self,
                                subparser,
                                description="Edit information and metadata in a .woz disk image",
                                epilog="""Tips:

 - Use repeated flags to edit multiple fields at once.
 - Use "key:" with no value to delete a metadata field.
 - Keys are case-sensitive.
 - Some values have format restrictions; read the .woz specification.""",
                                help=".woz disk image (modified in place)",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
        self.parser.add_argument("-i", "--info", type=str, action="append",
                                 help="""change information field.
INFO format is "key:value".
Acceptable keys are disk_type, write_protected, synchronized, cleaned, creator, version.
Additional keys for WOZ2 files are disk_sides, required_ram, boot_sector_format, compatible_hardware, optimal_bit_timing.
Other keys are ignored.
For boolean fields, use "1" or "true" or "yes" for true, "0" or "false" or "no" for false.""")
        self.parser.add_argument("-m", "--meta", type=str, action="append",
                                 help="""change metadata field.
META format is "key:value".
Standard keys are title, subtitle, publisher, developer, copyright, version, language, requires_ram,
requires_machine, notes, side, side_name, contributor, image_date. Other keys are allowed.""")

    def update(self, args):
        # 1st update version info field
        for i in args.info or ():
            k, v = i.split(":", 1)
            if k == "version":
                v = from_intish(v, WozINFOFormatError_BadVersion, "Unknown version (expected numeric value, found %s)")
                raise_if(v not in (1,2), WozINFOFormatError_BadVersion, "Unknown version (expected 1 or 2, found %s) % v")
                self.woz_image.woz_version = v
                self.woz_image.info["version"] = v

        # 2nd update disk_type info field
        for i in args.info or ():
            k, v = i.split(":", 1)
            if k == "disk_type":
                old_disk_type = self.woz_image.info["disk_type"]
                new_disk_type = self.woz_image.validate_info_disk_type(v)
                if old_disk_type != new_disk_type:
                    self.woz_image.info["disk_type"] = new_disk_type
                    self.woz_image.info["optimal_bit_timing"] = kDefaultBitTiming[new_disk_type]

        # then update all other info fields
        for i in args.info or ():
            k, v = i.split(":", 1)
            if k == "version": continue
            if k == "disk_type": continue
            if k == "write_protected":
                self.woz_image.info[k] = self.woz_image.validate_info_write_protected(v)
            elif k == "synchronized":
                self.woz_image.info[k] = self.woz_image.validate_info_synchronized(v)
            elif k == "cleaned":
                self.woz_image.info[k] = self.woz_image.validate_info_cleaned(v)
            elif k == "creator":
                self.woz_image.info[k] = self.woz_image.validate_info_creator(self.woz_image.encode_info_creator(v))
            if self.woz_image.info["version"] == 1: continue

            # remaining fields are only recognized in WOZ2 files (v2+ INFO chunk)
            if k == "disk_sides":
                self.woz_image.info[k] = self.woz_image.validate_info_disk_sides(v)
            elif k == "boot_sector_format":
                self.woz_image.info[k] = self.woz_image.validate_info_boot_sector_format(v)
            elif k == "optimal_bit_timing":
                self.woz_image.info[k] = self.woz_image.validate_info_optimal_bit_timing(v)
            elif k == "required_ram":
                if v.lower().endswith("k"):
                    # forgive user for typing "128K" instead of "128"
                    v = v[:-1]
                self.woz_image.info[k] = self.woz_image.validate_info_required_ram(v)
            elif k == "compatible_hardware":
                machines = v.split("|")
                for machine in machines:
                    self.woz_image.validate_metadata_requires_machine(machine)
                self.woz_image.info[k] = machines

        # add all new metadata fields, and delete empty ones
        for m in args.meta or ():
            k, v = m.split(":", 1)
            v = v.split("|")
            if len(v) == 1:
                v = v[0]
            if v:
                self.woz_image.meta[k] = v
            elif k in self.woz_image.meta.keys():
                del self.woz_image.meta[k]

class _CommandRemove(_WriterBaseCommand):
    def __init__(self):
        _WriterBaseCommand.__init__(self, "remove")

    def setup(self, subparser):
        _WriterBaseCommand.setup(self,
                                subparser,
                                description="Remove tracks from a 5.25-inch .woz disk image",
                                epilog="""Tips:

 - Tracks can be 0..40 in 0.25 increments (0, 0.25, 0.5, 0.75, 1, &c.)
 - Use repeated flags to remove multiple tracks at once.
 - It is harmless to try to remove a track that doesn't exist.""",
                                help=".woz disk image (modified in place)",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
        self.parser.add_argument("-t", "--track", type=str, action="append",
                                 help="""track to remove""")

    def update(self, args):
        raise_if(self.woz_image.info["disk_type"] != 1, WozINFOFormatError_BadDiskType, "Can not remove tracks from 3.5-inch disks")
        for i in args.track or ():
            self.woz_image.remove_track(float(i))

class _CommandImport(_WriterBaseCommand):
    def __init__(self):
        _WriterBaseCommand.__init__(self, "import")

    def setup(self, subparser):
        _WriterBaseCommand.setup(self, subparser,
                                description="Import JSON file to update metadata in a .woz disk image")

    def update(self, args):
        self.woz_image.from_json(sys.stdin.read())

def parse_args(args):
    cmds = [_CommandDump(), _CommandVerify(), _CommandEdit(), _CommandRemove(), _CommandExport(), _CommandImport()]
    parser = argparse.ArgumentParser(prog=__progname__,
                                     description="""A multi-purpose tool for manipulating .woz disk images.

See '""" + __progname__ + """ <command> -h' for help on individual commands.""",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=__displayname__)
    sp = parser.add_subparsers(dest="command", help="command")
    for command in cmds:
        command.setup(sp)
    if not args:
        parser.error("Command is required.")
    args = parser.parse_args(args)
    args.action(args)

if __name__ == "__main__":
    old_raise_if = raise_if
    raise_if = lambda cond, e, s="": cond and sys.exit("%s: %s" % (e.__name__, s))
    parse_args(sys.argv[1:])
