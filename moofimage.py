#!/usr/bin/env python3

#(c) 2022 by 4am
#license:MIT

import wozardry # https://github.com/a2-4am/wozardry
import bitarray # https://pypi.org/project/bitarray/
import sys

def myhex(b):
    return hex(b)[2:].rjust(2, "0").upper()

class MoofDiskImage(wozardry.WozDiskImage):
    def __init__(self, iostream=None):
        wozardry.WozDiskImage.__init__(self, iostream)
        for i,t in zip(range(len(self.tracks)), self.tracks):
            self.tracks[i] = MoofTrack(t.raw_bytes, t.raw_count)

class MoofTrack(wozardry.Track):
    def __init__(self, raw_bytes, raw_count):
        wozardry.Track.__init__(self, raw_bytes, raw_count)
        self.bit_index = 0
        self.revolutions = 0
        self.bits = bitarray.bitarray(endian="big")
        self.bits.frombytes(self.raw_bytes)
        while len(self.bits) > raw_count:
            self.bits.pop()

    def bit(self):
        b = self.bits[self.bit_index] and 1 or 0
        self.bit_index += 1
        if self.bit_index >= self.raw_count:
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

    def rewind(self, bit_count=1):
        self.bit_index -= bit_count
        if self.bit_index < 0:
            self.bit_index = self.raw_count - 1
            self.revolutions -= 1

    def find(self, sequence):
        starting_revolutions = self.revolutions
        seen = [0] * len(sequence)
        while (self.revolutions < starting_revolutions + 2):
            del seen[0]
            seen.append(next(self.nibble()))
            if tuple(seen) == tuple(sequence): return True
        return False

    def find_this_not_that(self, good, bad):
        starting_revolutions = self.revolutions
        good = tuple(good)
        bad = tuple(bad)
        seen_good = [0] * len(good)
        seen_bad = [0] * len(bad)
        while (self.revolutions < starting_revolutions + 2):
            del seen_good[0]
            del seen_bad[0]
            n = next(self.nibble())
            seen_good.append(n)
            seen_bad.append(n)
            if tuple(seen_bad) == bad: return False
            if tuple(seen_good) == good: return True
        return False

class MoofAddressField:
    def __init__(self, volume, track_id, sector_id, valid):
        self.volume = volume
        self.track_id = track_id
        self.sector_id = sector_id
        self.valid = valid

class MoofBlock:
    def __init__(self, address_field, decoded, start_bit_index=None, end_bit_index=None):
        self.address_field = address_field
        self.decoded = decoded
        self.start_bit_index = start_bit_index
        self.end_bit_index = end_bit_index

    def __getitem__(self, i):
        return self.decoded[i]

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
        self.expected_sectors_per_track = dict(zip(range(0xA0), (i for i in range(0x0C,0x07,-1) for j in range(0x20))))

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
        track_id = (h0 << 1) | ((h2 & 0b00000001) << 7) | ((h2 & 0b00100000) >> 5)
        return MoofAddressField(volume, track_id, sector_id, h0 ^ sector_id ^ h2 ^ volume == checksum)

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
        tag_bytes = [next(gcr_byte) for i in range(12)]
        decoded_bytes = [next(gcr_byte) for i in range(512)]

        # validate checksums against last data field nibble and three epilogue nibbles
        valid = nibble_groups[-1][-1] == ((c1 & 0b11000000) >> 6) | ((c2 & 0b11000000) >> 4) | ((c3 & 0b11000000) >> 2)
        valid &= self._(track) == (c3 & 0b00111111)
        valid &= self._(track) == (c2 & 0b00111111)
        valid &= self._(track) == (c1 & 0b00111111)

        return valid, sector_id, tag_bytes, decoded_bytes

    def verify_data_epilogue_at_point(self, track):
        return self.verify_nibbles_at_point(track, self.data_epilogue)

def driver(filename):
    with open(filename, 'rb') as f:
        mdisk = MoofDiskImage(f)
    rwts = MoofRWTS()
    for track_index in mdisk.tmap:
        if track_index == 0xFF: continue
        track = mdisk.tracks[track_index]
        seen_sectors = []
        track_id = -1
        while True:
            if not rwts.find_address_prologue(track): break
            address_field = rwts.address_field_at_point(track)
            if not address_field.valid: continue
            if (address_field.track_id < 0) or (address_field.track_id > 0x9F):
                print(f'/!\ invalid track ID {myhex(address_field.track_id)}')
                continue
            if (address_field.sector_id < 0) or \
               (address_field.sector_id > rwts.expected_sectors_per_track[address_field.track_id]):
                print(f'/!\ invalid sector ID {myhex(address_field.sector_id)}')
                continue
            if not rwts.verify_address_epilogue_at_point(track):
                print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: address epilogue does not match')
                continue
            if address_field.sector_id in seen_sectors: break
            seen_sectors.append(address_field.sector_id)
            bit_index = track.bit_index
            if not rwts.find_data_prologue(track):
                track.bit_index = bit_index
                if rwts.verify_nibbles_at_point(track, (0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xAB, 0xCD, 0xEF, 0xEF)):
                    print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: found PACE decryption key ', end='')
                    # extract PACE decryption key
                    for i in range(4):
                        next(track.nibble())
                    key = []
                    for i in range(4):
                        x = (next(track.nibble()) << 8) + next(track.nibble())
                        x = x & 0x5555
                        x = (x | (x >> 1)) & 0x3333
                        x = (x | (x >> 2)) & 0x0f0f
                        x = (x | (x >> 4)) & 0x00ff
                        x = (x | (x >> 8)) & 0xffff
                        key.append(x)
                    key.reverse()
                    for x in key:
                        print(myhex(x), end='')
                    print()
                continue
            try:
                valid, sector_id, tags, decoded_bytes = rwts.data_field_at_point(track)
            except KeyError:
                print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: invalid nibble')
                continue
            if not valid:
                print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: data checksums do not match')
                continue
            if valid:
                valid = address_field.sector_id == sector_id
            if not valid:
                print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: address/data field sector IDs do not match')
                continue
            valid = rwts.verify_data_epilogue_at_point(track)
            if not valid:
                print(f'/!\ track {myhex(address_field.track_id)}, sector {myhex(address_field.sector_id)}: data epilogue does not match')
                continue
            if (track_id == -1) and (address_field.valid):
                track_id = address_field.track_id
        if track_id == -1: continue
        sector_count = len(seen_sectors)
        expected_count = rwts.expected_sectors_per_track[track_id]
        if sector_count < expected_count:
            print(f'/!\ track {myhex(track_id)} only has {sector_count} sectors (expected {expected_count})')

if __name__ == '__main__':
    driver(sys.argv[1])
