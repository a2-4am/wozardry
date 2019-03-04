# `wozardry`

`wozardry` is a multi-purpose tool for manipulating `.woz` disk images. It can
validate file structure, edit metadata, import and export metadata in `JSON`
format, remove unused tracks, and provides a programmatic interface to "read"
bits and nibbles from a disk image. It supports both WOZ 1.0 and WOZ 2.0 files
and can convert files from one version to the other.

* [Installation](#installation)
* [Command line interface](#command-line-interface)
  * [`verify` command](#verify-command)
  * [`dump` command](#dump-command)
  * [`edit` command](#edit-command)
  * [How to convert WOZ1 to WOZ2 files](#how-to-convert-woz1-to-woz2-files)
  * [`import` and `export` commands](#import-and-export-commands)
  * [`remove` command](#remove-command)
* [Python interface](#python-interface)
  * [`WozDiskImage` interface](#wozdiskimage-interface)
  * [How to load and save files on disk](#how-to-load-and-save-files-on-disk)
  * [`Track` interface](#track-interface)

## Installation

`wozardry` is written in [Python 3](https://www.python.org).

It requires [bitarray](https://pypi.org/project/bitarray/), which can be
installed thusly:

```
$ pip3 install -U bitarray
```

(Developers who wish to run the test suite should also install the `pytest`
module with `pip3 install -U pytest`)

## Command line interface

wozardry is primarily designed to be used on the command line to directly
manipulate `.woz` disk images in place. It supports multiple commands, which are
listed in the `wozardry -h` output.

### `verify` command

This command verifies the file structure and metadata of a `.woz` disk image.
It produces no output unless a problem is found.

Sample usage:

```
$ wozardry verify "WOZ 2.0/DOS 3.3 System Master.woz"
```

**Tip**: you can [download a collection of .woz test
images](http://evolutioninteractive.com/applesauce/woz_images.zip).

The `verify` command does not "read" the data on the disk like an emulator
would. It merely verifies the structure of the `.woz` file itself and applies a
few sanity checks on the embedded metadata (if any). The disk may or may not
boot in an emulator. It may not pass its own copy protection checks. It may not
have the data you expected, or any data at all. `wozardry` can't answer those
questions.

### `dump` command

Prints all available information and metadata in a `.woz` disk image.

Sample usage:

```
$ wozardry dump "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
TMAP:  Track 0.00              TRKS 0
TMAP:  Track 0.25              TRKS 0
TMAP:  Track 0.75              TRKS 1
TMAP:  Track 1.00              TRKS 1
.
. [many lines elided]
.
TMAP:  Track 33.75             TRKS 34
TMAP:  Track 34.00             TRKS 34
TMAP:  Track 34.25             TRKS 34
META:  language:               English
META:  publisher:              Broderbund
META:  developer:
META:  side:                   Disk 1, Side A
META:  copyright:              1987
META:  requires_ram:           128K
META:  subtitle:
META:  image_date:             2018-01-15T01:30:53.025Z
META:  title:                  Wings of Fury
META:  version:
META:  contributor:            DiskBlitz
META:  notes:
META:  side_name:
META:  requires_machine:       2e
META:                          2c
META:                          2e+
META:                          2gs
INFO:  File format version:    2
INFO:  Disk type:              5.25-inch (140K)
INFO:  Write protected:        yes
INFO:  Tracks synchronized:    yes
INFO:  Weakbits cleaned:       yes
INFO:  Creator:                Applesauce v1.1
INFO:  Boot sector format:     1 (16-sector)
INFO:  Optimal bit timing:     32 (standard)
INFO:  Compatible hardware:    2e
INFO:                          2c
INFO:                          2e+
INFO:                          2gs
INFO:  Required RAM:           128K
INFO:  Largest track:          13 blocks
```

The `TMAP` section (stands for "track map") shows which tracks are included in
the disk image. As you can see from the above sample, the same bitstream data
can be assigned to multiple tracks, usually adjacent quarter tracks. Each
bitstream is stored only once in the `.woz` file.

The `META` section shows any embedded metadata, such as copyright and
version. This section is optional; not all `.woz` files will have the same
metadata fields, and some may have none at all.

The `INFO` section shows information that emulators or other programs might need
to know, such as the boot sector format (13- or 16-sector, or both) and whether
the disk is write protected. All `INFO` fields are required and are included in
every `.woz` file.

The output of the `dump` command is designed to by grep-able, if you're into
that kind of thing.

```
$ wozardry dump "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
```

will show just the `INFO` section.

**Tip**: [the .woz specification](https://applesaucefdc.com/woz/reference2/)
lists the standard metadata fields and the acceptable values of all info fields.

### `edit` command

This command lets you modify any information or metadata field in a `.woz`
file. This is where the fun(\*) starts.

(\*) not guaranteed, actual fun may vary

The inline help is a good overview.

```
usage: wozardry edit [-h] [-i INFO] [-m META] file

Edit information and metadata in a .woz disk image

positional arguments:
  file                  .woz disk image (modified in place)

optional arguments:
  -h, --help            show this help message and exit
  -i INFO, --info INFO  change information field. INFO format is "key:value".
                        Acceptable keys are disk_type, write_protected,
                        synchronized, cleaned, creator, version. Additional
                        keys for WOZ2 files are disk_sides, required_ram,
                        boot_sector_format, compatible_hardware,
                        optimal_bit_timing. Other keys are ignored. For
                        boolean fields, use "1" or "true" or "yes" for true,
                        "0" or "false" or "no" for false.
  -m META, --meta META  change metadata field. META format is "key:value".
                        Standard keys are title, subtitle, publisher,
                        developer, copyright, version, language, requires_ram,
                        requires_machine, notes, side, side_name, contributor,
                        image_date. Other keys are allowed.

Tips:

 - Use repeated flags to edit multiple fields at once.
 - Use "key:" with no value to delete a metadata field.
 - Keys are case-sensitive.
 - Some values have format restrictions; read the .woz specification.
```

Let's look at some examples.

Working with this same "Wings of Fury" disk image, let's give the game author
his due by adding the `developer` metadata field:

```
$ wozardry edit -m "developer:Steve Waldo" "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

Metadata fields are arbitrary; there is a standard set listed in [the .woz
specification](https://applesaucefdc.com/woz/reference2/), but you can add your
own.

```
$ wozardry edit -m "genre:action" -m "perspective:side view" "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

You can use a similar syntax to remove metadata fields that don't apply to this
disk.

```
$ wozardry edit -m "version:" -m "notes:" -m "side_name:" -m "subtitle:" "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

Now let's look at that metadata section again:

```
$ wozardry dump "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz" | grep "^META"
META:  language:               English
META:  publisher:              Broderbund
META:  developer:              Steve Waldo
META:  side:                   Disk 1, Side A
META:  copyright:              1987
META:  requires_ram:           128K
META:  image_date:             2018-01-15T01:30:53.025Z
META:  title:                  Wings of Fury
META:  contributor:            DiskBlitz
META:  requires_machine:       2e
META:                          2c
META:                          2e+
META:                          2gs
META:  genre:                  action
META:  perspective:            side view
```

You can modify `INFO` fields using a similar syntax (`-i` instead of `-m`), but
be aware that `INFO` fields are highly constrained, and incorrect values can
have noticeable effects in emulators. `wozardry` will reject any values that are
nonsensical or out of range, but even in-range values can render the disk image
unbootable. For example, the "optimal bit timing" field specifies the rate at
which bits appear in the floppy drive data latch; if the rate is not what the
disk's low-level RWTS code is expecting, the disk may be unable to read itself.

Nonetheless, here are some examples of changing `INFO` fields. To tell emulators
that a disk is not write-protected, set the `write_protected` field to `no`,
`false`, or `0`.

```
$ wozardry edit -i "write_protected:no" "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

To tell emulators that the disk only runs on certain Apple II models, set the
`compatible_hardware` field with a pipe-separated list. (Values may appear in
any order. See `kRequiresMachine` in the `wozardry` source code for all the
acceptable values.)

```
$ wozardry edit -i "compatible_hardware:2e|2e+|2c|2gs" "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

### How to convert WOZ1 to WOZ2 files

As of this writing, the `.woz` specification has undergone one major revision,
which changed the internal structure of a `.woz` file and added several new
`INFO` fields. Both file formats use the `.woz` file extension; they are
distinguished by magic bytes (`WOZ1` vs. `WOZ2`) within the file.

Let's say you have an older `WOZ1` file, like this one from the `WOZ 1.0`
directory of the official test images collection:

```
$ wozardry dump "WOZ 1.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
INFO:  File format version:    1
INFO:  Disk type:              5.25-inch (140K)
INFO:  Write protected:        yes
INFO:  Tracks synchronized:    yes
INFO:  Weakbits cleaned:       yes
INFO:  Creator:                Applesauce v0.29
```

The "file format version" confirms this is a `WOZ1` file. To convert it to a
`WOZ2` file, set the `version` field to `2`.

```
$ wozardry edit -i "version:2" "WOZ 1.0/Wings of Fury - Disk 1, Side A.woz"

$ wozardry dump "WOZ 1.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
INFO:  File format version:    2
INFO:  Disk type:              5.25-inch (140K)
INFO:  Write protected:        yes
INFO:  Tracks synchronized:    yes
INFO:  Weakbits cleaned:       yes
INFO:  Creator:                Applesauce v0.29
INFO:  Boot sector format:     0 (unknown)
INFO:  Optimal bit timing:     32 (standard)
INFO:  Compatible hardware:    unknown
INFO:  Required RAM:           unknown
INFO:  Largest track:          13 blocks
```

All the new (v2-specific) `INFO` fields are initialized with default
values. Existing fields like the write-protected flag are retained. ("Largest
track" is a calculated field and can not be set directly.)

### `import` and `export` commands

These commands allow you to access the information and metadata in a `.woz` file
in `JSON` format.

```
$ wozardry export "WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
{
  "woz": {
    "info": {
      "version": 2,
      "disk_type": 1,
      "write_protected": true,
      "synchronized": true,
      "cleaned": true,
      "creator": "Applesauce v1.1",
      "disk_sides": 1,
      "boot_sector_format": 1,
      "optimal_bit_timing": 32,
      "compatible_hardware": [
        "2e",
        "2c",
        "2e+",
        "2gs"
      ],
      "required_ram": 128,
      "largest_track": 13
    },
    "meta": {
      "language": "English",
      "publisher": "Broderbund",
      "developer": [
        ""
      ],
      "side": "Disk 1, Side A",
      "copyright": "1987",
      "requires_ram": "128K",
      "subtitle": [
        ""
      ],
      "image_date": "2018-01-15T01:30:53.025Z",
      "title": "Wings of Fury",
      "version": [
        ""
      ],
      "contributor": "DiskBlitz",
      "notes": [
        ""
      ],
      "side_name": [
        ""
      ],
      "requires_machine": [
        "2e",
        "2c",
        "2e+",
        "2gs"
      ]
    }
  }
}
```

You can pipe the output of the `export` command to the `import` command to copy
metadata from one `.woz` file to another.

```
$ wozardry export game-side-a.woz | wozardry import game-side-b.woz
```

Technically, this merges metadata. All metadata fields in `game-side-a.woz` will
be copied to `game-side-b.woz`, overwriting any existing values for those
fields. But if `game-side-b.woz` already had additional metadata fields that
were not present in `game-side-a.woz`, those will be retained.

**Tip**: [a2rchery](https://github.com/a2-4am/a2rchery) is a tool to manipulate
`.a2r` flux images. These `.a2r` files can also have embedded metadata, just
like `.woz` files. And guess what! `a2rchery` also has `import` and `export`
commands, just like `wozardry`. You see where this is going.

```
$ wozardry export game.woz | a2rchery import game.a2r
```

### `remove` command

This command allow you to remove one or more tracks from a `.woz` disk image.

Tracks are specified in quarter tracks, in base 10 (not base 16). Multiple
tracks can be removed at once.

```
$ wozardry remove -t0.25 -t0.5 -t0.75 -t1 -t1.25 -t35 "Gamma Goblins.woz"
```

**Note**: tracks are stored as indices in the `TMAP` chunk, and multiple tracks
can refer to the same bitstream (stored in the `TRKS` chunk). If you remove all
tracks that refer to a bitstream, the bitstream will be removed from the `TRKS`
chunk and all the indices in the `TMAP` chunk will be adjusted accordingly.

## Python interface

### `WozDiskImage` interface

This represents a single WOZ disk image. You can create it from scratch, load it
from a file on disk, or parse it from a bytestream in memory.

```
>>> import wozardry
>>> woz_image = wozardry.WozDiskImage()
>>> woz_image.woz_version
2
```

This newly created `woz_image` already has an `info` dictionary with all the
required fields in the `INFO` chunk.

```
>>> from pprint import pprint
>>> pprint(woz_image.info)
OrderedDict([('version', 2),
             ('disk_type', 1),
             ('write_protected', False),
             ('synchronized', False),
             ('cleaned', False),
             ('creator', 'wozardry 2.0-beta'),
             ('disk_sides', 1),
             ('boot_sector_format', 0),
             ('optimal_bit_timing', 32),
             ('compatible_hardware', []),
             ('required_ram', 0)])
>>> woz_image.info["compatible_hardware"] = ["2", "2+"]
>>> woz_image.info["compatible_hardware"]
['2', '2+']
```

It also has an empty `meta` dictionary for metadata.

```
>>> pprint(woz_image.meta)
OrderedDict()
>>> woz_image.meta["copyright"] = "1981"
>>> woz_image.meta["developer"] = "Chuckles"
>>> pprint(woz_image.meta)
OrderedDict([('copyright', '1981'),
             ('developer', 'Chuckles')])
```

### How to load and save files on disk

To load a `.woz` disk image from a file (or any file-like object), open the file
and pass it to the `WozDiskImage` constructor. Be sure to open files in binary
mode.

```
>>> with open("Wings of Fury.woz", "rb") as fp:
...     woz_image = wozardry.WozDiskImage(fp)
```

To save a file, serialize the `WozDiskImage` object with the `bytes()` method
and write that to disk. Be sure to open files in binary mode.

```
>>> with open("Wings of Fury.woz", "wb") as fp:
...     fp.write(bytes(woz_image))
```

### `Track` interface

A `.woz` disk image usually contains multiple tracks of data, otherwise what's
the point, right? Each track is accessed by the `Track` interface.

The `WozDiskImage.seek()` returns a `Track` object that contains that track's
data (or `None` if that track is not in the disk image).

**Tip**: the `seek()` method takes a logical track number, which could be a
quarter track or half track. To get the data on track 1.5, call `seek(1.5)`.

In this example, we load a `.woz` image from disk and seek to track 0:

```
>>> with open("Wings of Fury.woz", "rb") as fp:
...     woz_image = wozardry.WozDiskImage(fp)
>>> tr = woz_image.seek(0)
>>> tr
<wozardry.Track object at 0x108ccf3c8>
```

Now we can access the bitstream of the track. The raw bitstream is in `tr.bits`,
but you probably want to use one of these convenience methods instead.

To search the track for a specific nibble sequence, use the `find()` method. It
returns `True` if the nibble sequence was found, or `False` otherwise.

```
>>> tr.find(bytes.fromhex("D5 AA 96"))
True
```

The `Track` object maintains state of where it is within the bitstream
(`tr.bit_index`), including wrapping around to the beginning if it reaches the
end (`tr.revolutions`). After finding that `D5 AA 96` nibble sequence with the
`find()` method, we can read the next nibbles in the bitstream with the
`nibble()` generator.

```
>>> hex(next(tr.nibble()))
'0xff'
>>> hex(next(tr.nibble()))
'0xfe'
>>> hex(next(tr.nibble()))
'0xaa'
>>> hex(next(tr.nibble()))
'0xaa'
>>> hex(next(tr.nibble()))
'0xab'
>>> hex(next(tr.nibble()))
'0xaa'
```

**Tip**: the `nibble()` generator returns nibbles like a real disk controller.
`0` bits between nibbles are ignored, so the high bit of the returned nibble is
always `1`. The `find()` method uses the `nibble()` generator internally, so it
also ignores `0` bits between nibbles.

If you want to read individual bits from the current position in the bitstream,
use the `bit()` generator.

```
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
1
>>> next(tr.bit())
0
```

Unlike a real disk controller, you can move backwards in the bitstream, allowing
you to speculatively look at bits then rewind as if you hadn't seen them yet.

Let's rewind as if we hadn't just read those 8 individual bits, then read them
as a nibble:

```
>>> tr.rewind(8)
>>> hex(next(tr.nibble()))
'0xfe'
```
