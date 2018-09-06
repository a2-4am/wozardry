#!/usr/bin/env python3

# (c) 2018 by 4am
# MIT-licensed

import argparse
import binascii
import bitarray # https://pypi.org/project/bitarray/
import collections
import json
import itertools
import os

__version__ = "dev"
__date__ = "2018-09-06"
__progname__ = "wozardry"
__displayname__ = __progname__ + " " + __version__ + " by 4am (" + __date__ + ")"

# domain-specific constants defined in .woz specification
kWOZ1 = b"WOZ1"
kINFO = b"INFO"
kTMAP = b"TMAP"
kTRKS = b"TRKS"
kMETA = b"META"
kBitstreamLengthInBytes = 6646
kLanguages = ("English","Spanish","French","German","Chinese","Japanese","Italian","Dutch","Portuguese","Danish","Finnish","Norwegian","Swedish","Russian","Polish","Turkish","Arabic","Thai","Czech","Hungarian","Catalan","Croatian","Greek","Hebrew","Romanian","Slovak","Ukranian","Indonesian","Malay","Vietnamese","Other")
kRequiresRAM = ("16K","24K","32K","48K","64K","128K","256K","512K","768K","1M","1.25M","1.5M+","Unknown")
kRequiresMachine = ("2","2+","2e","2c","2e+","2gs","2c+","3","3+")

# strings and things, for print routines and error messages
sEOF = "Unexpected EOF"
sBadChunkSize = "Bad chunk size"
dNoYes = {False:"no",True:"yes"}
tQuarters = (".00",".25",".50",".75")

# errors that may be raised
class WozError(Exception): pass # base class
class WozCRCError(WozError): pass
class WozFormatError(WozError): pass
class WozEOFError(WozFormatError): pass
class WozHeaderError(WozFormatError): pass
class WozHeaderError_NoWOZ1(WozHeaderError): pass
class WozHeaderError_NoFF(WozHeaderError): pass
class WozHeaderError_NoLF(WozHeaderError): pass
class WozINFOFormatError(WozFormatError): pass
class WozINFOFormatError_BadVersion(WozINFOFormatError): pass
class WozINFOFormatError_BadDiskType(WozINFOFormatError): pass
class WozINFOFormatError_BadWriteProtected(WozINFOFormatError): pass
class WozINFOFormatError_BadSynchronized(WozINFOFormatError): pass
class WozINFOFormatError_BadCleaned(WozINFOFormatError): pass
class WozINFOFormatError_BadCreator(WozINFOFormatError): pass
class WozTMAPFormatError(WozFormatError): pass
class WozTMAPFormatError_BadTRKS(WozTMAPFormatError): pass
class WozTRKSFormatError(WozFormatError): pass
class WozMETAFormatError(WozFormatError): pass
class WozMETAFormatError_DuplicateKey(WozFormatError): pass
class WozMETAFormatError_BadValue(WozFormatError): pass
class WozMETAFormatError_BadLanguage(WozFormatError): pass
class WozMETAFormatError_BadRAM(WozFormatError): pass
class WozMETAFormatError_BadMachine(WozFormatError): pass

def from_uint32(b):
    return int.from_bytes(b, byteorder="little")
from_uint16=from_uint32

def to_uint32(b):
    return b.to_bytes(4, byteorder="little")

def to_uint16(b):
    return b.to_bytes(2, byteorder="little")

def to_uint8(b):
    return b.to_bytes(1, byteorder="little")

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

class WozTrack(Track):
    def __init__(self, bits, bit_count, splice_point = 0xFFFF, splice_nibble = 0, splice_bit_count = 0):
        Track.__init__(self, bits, bit_count)
        self.splice_point = splice_point
        self.splice_nibble = splice_nibble
        self.splice_bit_count = splice_bit_count

class DiskImage: # base class
    def __init__(self, filename=None, stream=None):
        raise_if(not filename and not stream, WozError, "no input")
        self.filename = filename
        self.tracks = []

    def seek(self, track_num):
        """returns Track object for the given track, or None if the track is not part of this disk image. track_num can be 0..40 in 0.25 increments (0, 0.25, 0.5, 0.75, 1, &c.)"""
        return None

class WozValidator:
    def validate_info_version(self, version):
        raise_if(version != b'\x01', WozINFOFormatError_BadVersion, "Unknown version (expected 1, found %s)" % version)

    def validate_info_disk_type(self, disk_type):
        raise_if(disk_type not in (b'\x01',b'\x02'), WozINFOFormatError_BadDiskType, "Unknown disk type (expected 1 or 2, found %s)" % disk_type)

    def validate_info_write_protected(self, write_protected):
        raise_if(write_protected not in (b'\x00',b'\x01'), WozINFOFormatError_BadWriteProtected, "Unknown write protected flag (expected 0 or 1, found %s)" % write_protected)

    def validate_info_synchronized(self, synchronized):
        raise_if(synchronized not in (b'\x00',b'\x01'), WozINFOFormatError_BadSynchronized, "Unknown synchronized flag (expected 0, or 1, found %s)" % synchronized)

    def validate_info_cleaned(self, cleaned):
        raise_if(cleaned not in (b'\x00',b'\x01'), WozINFOFormatError_BadCleaned, "Unknown cleaned flag (expected 0 or 1, found %s)" % cleaned)

    def validate_info_creator(self, creator_as_bytes):
        raise_if(len(creator_as_bytes) > 32, WozINFOFormatError_BadCreator, "Creator is longer than 32 bytes")
        try:
            creator_as_bytes.decode("UTF-8")
        except:
            raise_if(True, WozINFOFormatError_BadCreator, "Creator is not valid UTF-8")

    def encode_info_creator(self, creator_as_string):
        creator_as_bytes = creator_as_string.encode("UTF-8").ljust(32, b" ")
        self.validate_info_creator(creator_as_bytes)
        return creator_as_bytes

    def decode_info_creator(self, creator_as_bytes):
        self.validate_info_creator(creator_as_bytes)
        return creator_as_bytes.decode("UTF-8").strip()

    def validate_metadata(self, metadata_as_bytes):
        try:
            metadata = metadata_as_bytes.decode("UTF-8")
        except:
            raise WozMETAFormatError("Metadata is not valid UTF-8")

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

class WozReader(DiskImage, WozValidator):
    def __init__(self, filename=None, stream=None):
        DiskImage.__init__(self, filename, stream)
        self.tmap = None
        self.info = collections.OrderedDict()
        self.meta = collections.OrderedDict()

        with stream or open(filename, "rb") as f:
            header_raw = f.read(8)
            raise_if(len(header_raw) != 8, WozEOFError, sEOF)
            self.__process_header(header_raw)
            crc_raw = f.read(4)
            raise_if(len(crc_raw) != 4, WozEOFError, sEOF)
            crc = from_uint32(crc_raw)
            all_data = []
            while True:
                chunk_id = f.read(4)
                if not chunk_id: break
                raise_if(len(chunk_id) != 4, WozEOFError, sEOF)
                all_data.append(chunk_id)
                chunk_size_raw = f.read(4)
                raise_if(len(chunk_size_raw) != 4, WozEOFError, sEOF)
                all_data.append(chunk_size_raw)
                chunk_size = from_uint32(chunk_size_raw)
                data = f.read(chunk_size)
                raise_if(len(data) != chunk_size, WozEOFError, sEOF)
                all_data.append(data)
                if chunk_id == kINFO:
                    raise_if(chunk_size != 60, WozINFOFormatError, sBadChunkSize)
                    self.__process_info(data)
                elif chunk_id == kTMAP:
                    raise_if(chunk_size != 160, WozTMAPFormatError, sBadChunkSize)
                    self.__process_tmap(data)
                elif chunk_id == kTRKS:
                    self.__process_trks(data)
                elif chunk_id == kMETA:
                    self.__process_meta(data)
            if crc:
                raise_if(crc != binascii.crc32(b"".join(all_data)) & 0xffffffff, WozCRCError, "Bad CRC")

    def __process_header(self, data):
        raise_if(data[:4] != kWOZ1, WozHeaderError_NoWOZ1, "Magic string 'WOZ1' not present at offset 0")
        raise_if(data[4] != 0xFF, WozHeaderError_NoFF, "Magic byte 0xFF not present at offset 4")
        raise_if(data[5:8] != b"\x0A\x0D\x0A", WozHeaderError_NoLF, "Magic bytes 0x0A0D0A not present at offset 5")

    def __process_info(self, data):
        version = data[0]
        self.validate_info_version(to_uint8(version))
        disk_type = data[1]
        self.validate_info_disk_type(to_uint8(disk_type))
        write_protected = data[2]
        self.validate_info_write_protected(to_uint8(write_protected))
        synchronized = data[3]
        self.validate_info_synchronized(to_uint8(synchronized))
        cleaned = data[4]
        self.validate_info_cleaned(to_uint8(cleaned))
        creator = self.decode_info_creator(data[5:37])
        self.info["version"] = version # int
        self.info["disk_type"] = disk_type # int
        self.info["write_protected"] = (write_protected == 1) # boolean
        self.info["synchronized"] = (synchronized == 1) # boolean
        self.info["cleaned"] = (cleaned == 1) # boolean
        self.info["creator"] = creator # string

    def __process_tmap(self, data):
        self.tmap = list(data)

    def __process_trks(self, data):
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
            self.tracks.append(WozTrack(bits, bit_count, splice_point, splice_nibble, splice_bit_count))
        for trk, i in zip(self.tmap, itertools.count()):
            raise_if(trk != 0xFF and trk >= len(self.tracks), WozTMAPFormatError_BadTRKS, "Invalid TMAP entry: track %d%s points to non-existent TRKS chunk %d" % (i/4, tQuarters[i%4], trk))

    def __process_meta(self, metadata_as_bytes):
        metadata = self.decode_metadata(metadata_as_bytes)
        for line in metadata.split("\n"):
            if not line: continue
            columns_raw = line.split("\t")
            raise_if(len(columns_raw) != 2, WozMETAFormatError, "Malformed metadata")
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

    def to_json(self):
        j = {"woz": {"info":self.info, "meta":self.meta}}
        return json.dumps(j, indent=2)

    def seek(self, track_num):
        """returns Track object for the given track, or None if the track is not part of this disk image. track_num can be 0..40 in 0.25 increments (0, 0.25, 0.5, 0.75, 1, &c.)"""
        if type(track_num) != float:
            track_num = float(track_num)
        if track_num < 0.0 or \
           track_num > 40.0 or \
           track_num.as_integer_ratio()[1] not in (1,2,4):
            raise WozError("Invalid track %s" % track_num)
        trk_id = self.tmap[int(track_num * 4)]
        if trk_id == 0xFF: return None
        return self.tracks[trk_id]

class WozWriter(WozValidator):
    def __init__(self, creator):
        self.info = collections.OrderedDict()
        self.info["version"] = 1
        self.info["disk_type"] = 1
        self.info["write_protected"] = False
        self.info["synchronized"] = False
        self.info["cleaned"] = False
        self.info["creator"] = creator
        self.tracks = []
        self.tmap = [0xFF]*160
        self.meta = collections.OrderedDict()

    def add_track(self, track_num, track):
        tmap_id = int(track_num * 4)
        trk_id = len(self.tracks)
        self.tracks.append(track)
        self.tmap[tmap_id] = trk_id
        if tmap_id:
            self.tmap[tmap_id - 1] = trk_id
        if tmap_id < 159:
            self.tmap[tmap_id + 1] = trk_id

    def from_json(self, json_string):
        j = json.loads(json_string)
        root = [x for x in j.keys()].pop()
        self.info.update(j[root]["info"])
        self.meta.update(j[root]["meta"])

    def build_info(self):
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
        chunk.extend(version_raw) # version (int, probably 1)
        chunk.extend(disk_type_raw) # disk type (1=5.25 inch, 2=3.5 inch)
        chunk.extend(write_protected_raw) # write-protected (0=no, 1=yes)
        chunk.extend(synchronized_raw) # tracks synchronized (0=no, 1=yes)
        chunk.extend(cleaned_raw) # weakbits cleaned (0=no, 1=yes)
        chunk.extend(creator_raw) # creator
        chunk.extend(b"\x00" * 23) # reserved
        return chunk

    def build_tmap(self):
        chunk = bytearray()
        chunk.extend(kTMAP) # chunk ID
        chunk.extend(to_uint32(160)) # chunk size
        chunk.extend(bytes(self.tmap))
        return chunk

    def build_trks(self):
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

    def build_meta(self):
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
             for k, v in meta_tmp.items()])
        chunk = bytearray()
        chunk.extend(kMETA) # chunk ID
        chunk.extend(to_uint32(len(data))) # chunk size
        chunk.extend(data)
        return chunk

    def build_head(self, crc):
        chunk = bytearray()
        chunk.extend(kWOZ1) # magic bytes
        chunk.extend(b"\xFF\x0A\x0D\x0A") # more magic bytes
        chunk.extend(to_uint32(crc)) # CRC32 of rest of file (calculated in caller)
        return chunk

    def write(self, stream):
        info = self.build_info()
        tmap = self.build_tmap()
        trks = self.build_trks()
        meta = self.build_meta()
        crc = binascii.crc32(info + tmap + trks + meta)
        head = self.build_head(crc)
        stream.write(head)
        stream.write(info)
        stream.write(tmap)
        stream.write(trks)
        stream.write(meta)

#---------- command line interface ----------

class BaseCommand:
    def __init__(self, name):
        self.name = name

    def setup(self, subparser, description=None, epilog=None, help=".woz disk image", formatter_class=argparse.HelpFormatter):
        self.parser = subparser.add_parser(self.name, description=description, epilog=epilog, formatter_class=formatter_class)
        self.parser.add_argument("file", help=help)
        self.parser.set_defaults(action=self)

    def __call__(self, args):
        self.woz_image = WozReader(args.file)

class CommandVerify(BaseCommand):
    def __init__(self):
        BaseCommand.__init__(self, "verify")

    def setup(self, subparser):
        BaseCommand.setup(self, subparser,
                          description="Verify file structure and metadata of a .woz disk image (produces no output unless a problem is found)")

class CommandDump(BaseCommand):
    kWidth = 30

    def __init__(self):
        BaseCommand.__init__(self, "dump")

    def setup(self, subparser):
        BaseCommand.setup(self, subparser,
                          description="Print all available information and metadata in a .woz disk image")

    def __call__(self, args):
        BaseCommand.__call__(self, args)
        self.print_tmap()
        self.print_meta()
        self.print_info()

    def print_info(self):
        print("INFO:  File format version:".ljust(self.kWidth), "%d" % self.woz_image.info["version"])
        print("INFO:  Disk type:".ljust(self.kWidth),           ("5.25-inch", "3.5-inch")[self.woz_image.info["disk_type"]-1])
        print("INFO:  Write protected:".ljust(self.kWidth),     dNoYes[self.woz_image.info["write_protected"]])
        print("INFO:  Track synchronized:".ljust(self.kWidth),  dNoYes[self.woz_image.info["synchronized"]])
        print("INFO:  Weakbits cleaned:".ljust(self.kWidth),    dNoYes[self.woz_image.info["cleaned"]])
        print("INFO:  Creator:".ljust(self.kWidth),             self.woz_image.info["creator"])

    def print_tmap(self):
        i = 0
        for trk, i in zip(self.woz_image.tmap, itertools.count()):
            if trk != 0xFF:
                print(("TMAP:  Track %d%s" % (i/4, tQuarters[i%4])).ljust(self.kWidth), "TRKS %d" % (trk))

    def print_meta(self):
        if not self.woz_image.meta: return
        for key, values in self.woz_image.meta.items():
            if type(values) == str:
                values = [values]
            print(("META:  " + key + ":").ljust(self.kWidth), values[0])
            for value in values[1:]:
                print("META:  ".ljust(self.kWidth), value)

class CommandExport(BaseCommand):
    def __init__(self):
        BaseCommand.__init__(self, "export")

    def setup(self, subparser):
        BaseCommand.setup(self, subparser,
                          description="Export (as JSON) all information and metadata from a .woz disk image")

    def __call__(self, args):
        BaseCommand.__call__(self, args)
        print(self.woz_image.to_json())

class WriterBaseCommand(BaseCommand):
    def __call__(self, args):
        BaseCommand.__call__(self, args)
        self.args = args
        # maintain creator if there is one, otherwise use default
        self.output = WozWriter(self.woz_image.info.get("creator", __displayname__))
        self.output.tmap = self.woz_image.tmap
        self.output.tracks = self.woz_image.tracks
        self.output.info = self.woz_image.info.copy()
        self.output.meta = self.woz_image.meta.copy()
        self.update()
        tmpfile = args.file + ".ardry"
        with open(tmpfile, "wb") as f:
            self.output.write(f)
        os.rename(tmpfile, args.file)

class CommandEdit(WriterBaseCommand):
    def __init__(self):
        WriterBaseCommand.__init__(self, "edit")

    def setup(self, subparser):
        WriterBaseCommand.setup(self,
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
Other keys are ignored.
For boolean fields, use "1" or "true" or "yes" for true, "0" or "false" or "no" for false.""")
        self.parser.add_argument("-m", "--meta", type=str, action="append",
                                 help="""change metadata field.
META format is "key:value".
Standard keys are title, subtitle, publisher, developer, copyright, version, language, requires_ram,
requires_machine, notes, side, side_name, contributor, image_date. Other keys are allowed.""")

    def update(self):
        # add all new info fields
        for i in self.args.info or ():
            k, v = i.split(":", 1)
            if k in ("write_protected","synchronized","cleaned"):
                v = v.lower() in ("1", "true", "yes")
            self.output.info[k] = v
        # add all new metadata fields, and delete empty ones
        for m in self.args.meta or ():
            k, v = m.split(":", 1)
            v = v.split("|")
            if len(v) == 1:
                v = v[0]
            if v:
                self.output.meta[k] = v
            elif k in self.output.meta.keys():
                del self.output.meta[k]

class CommandImport(WriterBaseCommand):
    def __init__(self):
        WriterBaseCommand.__init__(self, "import")

    def setup(self, subparser):
        WriterBaseCommand.setup(self, subparser,
                                description="Import JSON file to update information and metadata in a .woz disk image")

    def update(self):
        self.output.from_json(sys.stdin.read())

if __name__ == "__main__":
    import sys
    raise_if = lambda cond, e, s="": cond and sys.exit("%s: %s" % (e.__name__, s))
    cmds = [CommandDump(), CommandVerify(), CommandEdit(), CommandExport(), CommandImport()]
    parser = argparse.ArgumentParser(prog=__progname__,
                                     description="""A multi-purpose tool for manipulating .woz disk images.

See '""" + __progname__ + """ <command> -h' for help on individual commands.""",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action="version", version=__displayname__)
    sp = parser.add_subparsers(dest="command", help="command")
    for command in cmds:
        command.setup(sp)
    args = parser.parse_args()
    args.action(args)
