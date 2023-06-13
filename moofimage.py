#!/usr/bin/env python3

#(c) 2022 by 4am
#license:MIT

import wozardry # https://github.com/a2-4am/wozardry
import bitarray # https://pypi.org/project/bitarray/
import sys

def myhex(b):
    return hex(b)[2:].rjust(2, "0").upper()

class MoofTrack(wozardry.Track):
    def __init__(self, raw_bytes, raw_count):
        wozardry.Track.__init__(self, raw_bytes, raw_count)

class MoofAddressField:
    def __init__(self, valid, volume, track_id, sector_id):
        self.valid = valid
        self.volume = volume
        self.track_id = track_id
        self.sector_id = sector_id

class MoofDataField:
    def __init__(self, valid, sector_id, tags, data):
        self.valid = valid
        self.sector_id = sector_id
        self.tags = tags
        self.data = data

class MoofBlock:
    def __init__(self, address_field, data_field):
        self.address_field = address_field
        self.data_field = data_field

class MoofRWTS:
    kDefaultAddressPrologue16 = (0xD5, 0xAA, 0x96)
    kDefaultAddressEpilogue16 = (0xDE, 0xAA)
    kDefaultDataPrologue16 =    (0xD5, 0xAA, 0xAD)
    kDefaultDataEpilogue16 =    (0xDE, 0xAA)
    kDefaultNibbleTranslationTable16 = {
        0x96: 0x00, 0x97: 0x01, 0x9A: 0x02, 0x9B: 0x03, 0x9D: 0x04, 0x9E: 0x05, 0x9F: 0x06, 0xA6: 0x07,
        0xA7: 0x08, 0xAB: 0x09, 0xAC: 0x0A, 0xAD: 0x0B, 0xAE: 0x0C, 0xAF: 0x0D, 0xB2: 0x0E, 0xB3: 0x0F,
        0xB4: 0x10, 0xB5: 0x11, 0xB6: 0x12, 0xB7: 0x13, 0xB9: 0x14, 0xBA: 0x15, 0xBB: 0x16, 0xBC: 0x17,
        0xBD: 0x18, 0xBE: 0x19, 0xBF: 0x1A, 0xCB: 0x1B, 0xCD: 0x1C, 0xCE: 0x1D, 0xCF: 0x1E, 0xD3: 0x1F,
        0xD6: 0x20, 0xD7: 0x21, 0xD9: 0x22, 0xDA: 0x23, 0xDB: 0x24, 0xDC: 0x25, 0xDD: 0x26, 0xDE: 0x27,
        0xDF: 0x28, 0xE5: 0x29, 0xE6: 0x2A, 0xE7: 0x2B, 0xE9: 0x2C, 0xEA: 0x2D, 0xEB: 0x2E, 0xEC: 0x2F,
        0xED: 0x30, 0xEE: 0x31, 0xEF: 0x32, 0xF2: 0x33, 0xF3: 0x34, 0xF4: 0x35, 0xF5: 0x36, 0xF6: 0x37,
        0xF7: 0x38, 0xF9: 0x39, 0xFA: 0x3A, 0xFB: 0x3B, 0xFC: 0x3C, 0xFD: 0x3D, 0xFE: 0x3E, 0xFF: 0x3F,
    }

    def __init__(self,
                 address_prologue = kDefaultAddressPrologue16,
                 address_epilogue = kDefaultAddressEpilogue16,
                 data_prologue = kDefaultDataPrologue16,
                 data_epilogue = kDefaultDataEpilogue16,
                 nibble_translate_table = kDefaultNibbleTranslationTable16):
        self.address_prologue = address_prologue
        self.address_epilogue = address_epilogue
        self.data_prologue = data_prologue
        self.data_epilogue = data_epilogue
        self.nibble_translate_table = nibble_translate_table
        self.sectors_per_track = dict(zip(range(0xA0), (i for i in range(0x0C,0x07,-1) for j in range(0x20))))

    def _(self, track):
        return self.nibble_translate_table[next(track.nibble())]

    def find_address_prologue(self, track):
        return track.find(self.address_prologue)

    def address_field_at_point(self, track):
        h0 = self._(track)
        sector_id = self._(track)
        h2 = self._(track)
        volume = self._(track)
        checksum = self._(track)
        valid = h0 ^ sector_id ^ h2 ^ volume == checksum
        track_id = (h0 << 1) | ((h2 & 0b00000001) << 7) | ((h2 & 0b00100000) >> 5)
        return MoofAddressField(valid, volume, track_id, sector_id)

    def verify_nibbles_at_point(self, track, nibbles):
        found = []
        for i in nibbles:
            found.append(next(track.nibble()))
        return tuple(found) == tuple(nibbles)

    def verify_address_epilogue_at_point(self, track):
        return self.verify_nibbles_at_point(track, self.address_epilogue)

    def find_data_prologue(self, track):
        return track.find_this_not_that(self.data_prologue, self.address_prologue)

    def data_field_at_point(self, track):
        # three checksums
        c1 = c2 = c3 = 0

        # generator to decode grouped bytes while juggling three checksums
        def gcr_generator(byte_groups):
            nonlocal c1, c2, c3
            for d0, d1, d2 in byte_groups:
                c1 = (c1 & 0b11111111) << 1
                if c1 > 0xFF:
                    c1 -= 0xFF
                    c3 += 1
                b = d0 ^ c1
                c3 += b
                yield b

                if c3 > 0xFF:
                    c3 &= 0b11111111
                    c2 += 1
                b = d1 ^ c3
                c2 += b
                yield b

                if c2 > 0xFF:
                    c2 &= 0b11111111
                    c1 += 1
                b = d2 ^ c2
                c1 += b
                yield b

        # first nibble is sector number
        sector_id = self._(track)

        # read 700 nibbles, decode each against nibble translate table, store in 175 groups of 4
        nibble_groups = [(self._(track), self._(track), self._(track), self._(track))
                         for i in range(175)]

        # convert each group of 4 nibbles into a group of 3 bytes to pass into the decoder
        gcr_byte = gcr_generator((((n[1] & 0b00111111) | ((n[0] << 2) & 0b11000000),
                                   (n[2] & 0b00111111) | ((n[0] << 4) & 0b11000000),
                                   (n[3] & 0b00111111) | ((n[0] << 6) & 0b11000000))
                                  for n in nibble_groups))

        # decode 524 bytes (12 tag bytes + 512 data bytes)
        tags = [next(gcr_byte) for i in range(12)]
        data = [next(gcr_byte) for i in range(512)]

        # validate checksums against last data field nibble and three epilogue nibbles
        valid = nibble_groups[-1][-1] == ((c1 & 0b11000000) >> 6) | ((c2 & 0b11000000) >> 4) | ((c3 & 0b11000000) >> 2)
        valid &= self._(track) == (c3 & 0b00111111)
        valid &= self._(track) == (c2 & 0b00111111)
        valid &= self._(track) == (c1 & 0b00111111)

        return MoofDataField(valid, sector_id, tags, data)

    def verify_data_epilogue_at_point(self, track):
        return self.verify_nibbles_at_point(track, self.data_epilogue)

class DefaultLogger:
    def warn(self, message, T=None, S=None, X=None, Y=None):
        if T: T = myhex(T)
        if S: S = myhex(S)
        message = message.format(**locals())
        sys.stderr.write(message)
        sys.stderr.write('\n')
    info=warn
    error=warn

class MoofDiskImage(wozardry.WozDiskImage):
    kE7Bytestream = (0x2B, 0x00, 0x2B, 0xFD, 0x83, 0x6F, 0x20, 0xE2,
                     0x8D, 0x99, 0x49, 0x44, 0x47, 0x82, 0xD9, 0x26,
                     0xFB, 0xC6, 0x3, 0xF8)
    kPACEPrologue = (0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                     0xFF, 0xFF, 0xFF, 0xFF, 0xAB, 0xCD, 0xEF, 0xEF)

    def __init__(self, iostream=None, rwtsclass=MoofRWTS, loggerclass=DefaultLogger):
        wozardry.WozDiskImage.__init__(self, iostream)
        self.logger = loggerclass()
        self.rwts = rwtsclass()
        for i,t in zip(range(len(self.tracks)), self.tracks):
            self.tracks[i] = MoofTrack(t.raw_bytes, t.raw_count)
        self.parse()

    def get_pace_key_at_point(self, track, bit_index):
        # save bitstream position
        track.bit_index, bit_index = bit_index, track.bit_index
        key = []
        if self.rwts.verify_nibbles_at_point(track, self.kPACEPrologue):
            for i in range(4):
                next(track.nibble())
            for i in range(4):
                x = (next(track.nibble()) << 8) + next(track.nibble())
                x = x & 0x5555
                x = (x | (x >> 1)) & 0x3333
                x = (x | (x >> 2)) & 0x0f0f
                x = (x | (x >> 4)) & 0x00ff
                x = (x | (x >> 8)) & 0xffff
                key.append(x)
            key.reverse()
        # restore bitstream position
        track.bit_index, bit_index = bit_index, track.bit_index
        return "".join(map(myhex, key))

    def parse(self):
        self.blocks = []
        # only 400K and 800K disks supported at the moment
        if not self.info["disk_type"] in (1,2): return
        for track_index in self.tmap:
            if track_index == 0xFF: continue
            track = self.tracks[track_index]
            seen_sectors = []
            track_id = -1
            while self.rwts.find_address_prologue(track):
                address_field = self.rwts.address_field_at_point(track)

                # log if address field checksum doesn't match
                if not address_field.valid:
                    self.logger.warn(
                        'T{T},S{S} Address field checksum invalid',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                # log if track ID is ridiculous
                if not (0x00 <= address_field.track_id <= 0x9F):
                    self.logger.warn(
                        'Address field track ID {T} invalid',
                        T=address_field.track_id
                    )
                    continue

                # log if sector ID is ridiculous
                if not (0x00 <= address_field.sector_id < self.rwts.sectors_per_track[address_field.track_id]):
                    self.logger.warn(
                        'Address field sector ID {S} invalid',
                        S=address_field.sector_id
                    )
                    continue

                # log if address field epilogue isn't next
                if not self.rwts.verify_address_epilogue_at_point(track):
                    self.logger.warn(
                        'T{T},S{S} Address field epilogue invalid',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                # if we see duplicate sector IDs, assume we're done
                if address_field.sector_id in seen_sectors: break
                seen_sectors.append(address_field.sector_id)

                old_bit_index = track.bit_index
                if not self.rwts.find_data_prologue(track):
                    # if we didn't find any data field prologue at all
                    # before the next address field prologue, then check
                    # if this is a specially formatted protection sector
                    # from which we can extract some useful information
                    decryption_key = self.get_pace_key_at_point(track, old_bit_index)
                    if decryption_key:
                        self.logger.info(
                            'T{T},S{S} Found PACE protection, key={X}',
                            T=address_field.track_id,
                            S=address_field.sector_id,
                            X=decryption_key
                        )
                    continue

                try:
                    data_field = self.rwts.data_field_at_point(track)
                except KeyError:
                    # log if GCR decoding failed
                    self.logger.warn(
                        'T{T},S{S} Data field contains invalid nibble',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                # log if checksums didn't match after GCR decoding
                if not data_field.valid:
                    self.logger.warn(
                        'T{T},S{S} Data field checksums invalid',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                # address and data fields are supposed to contain
                # matching sector IDs, so log if they don't match
                if address_field.sector_id != data_field.sector_id:
                    self.logger.warn(
                        'T{T},S{S} Address and data field sector IDs do not match',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                # log if sector data contains E7 bitstream
                if (sum(data_field.data[:0x18E]) == 0) and (tuple(data_field.data[0x18F:0x1A3]) == self.kE7Bytestream):
                    #print(data_field.data[0x18F:0x1A3])
                    self.logger.warn(
                        'T{T},S{S} Found E7 bitstream',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )

                # log if data field epilogue isn't next
                if not self.rwts.verify_data_epilogue_at_point(track):
                    self.logger.warn(
                        'T{T},S{S} Data field epilogue invalid',
                        T=address_field.track_id,
                        S=address_field.sector_id
                    )
                    continue

                track_id = address_field.track_id
                self.blocks.append(MoofBlock(address_field, data_field))

            # move on if we didn't find any valid sectors
            if track_id == -1: continue

            # log if we didn't find enough sectors
            sector_count = len(seen_sectors)
            expected_count = self.rwts.sectors_per_track[track_id]
            if sector_count < expected_count:
                self.logger.warn(
                    'T{T} Found {X} sectors (expected {Y})',
                    T=track_id,
                    X=sector_count,
                    Y=expected_count
                )

def driver(filename):
    with open(filename, 'rb') as f:
        mdisk = MoofDiskImage(f)

if __name__ == '__main__':
    driver(sys.argv[1])
