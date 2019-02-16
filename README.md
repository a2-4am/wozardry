# Command line usage

wozardry is primarily designed to be used on the command line to directly manipulate `.woz` disk images. It supports multiple commands, which are listed in the `wozardry -h` output.

## `verify` command

This command verifies the file structure and metadata of a `.woz` disk image.  It produces no output unless a problem is found.

Sample usage:

```
$ wozardry verify "woz test images/WOZ 2.0/DOS 3.3 System Master.woz"
```

**Tip**: you can [download a collection of .woz test images](http://evolutioninteractive.com/applesauce/woz_images.zip).

The `verify` command does not "read" the data on the disk like an emulator would. It merely verifies the structure of the `.woz` file itself and applies a few sanity checks on the embedded metadata (if any). The disk may or may not boot in an emulator. It may not pass its own copy protection checks. It may not have the data you expected, or any data at all. `wozardry` can't answer those questions.

## `dump` command

Prints all available information and metadata in a `.woz` disk image.

Sample usage:

```
$ wozardry dump "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
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

The `TMAP` section (stands for "track map") shows which tracks are included in the disk image. As you can see from the above sample, the same bitstream data can be assigned to multiple tracks, usually adjacent quarter tracks. Each bitstream is stored only once in the `.woz` file.

The `META` section shows any embedded metadata, such as copyright and version. This section is optional; not all `.woz` files will have the same metadata fields, and some may have none at all.

The `INFO` section shows information that emulators or other programs might need to know, such as the boot sector format (13- or 16-sector, or both) and whether the disk is write protected. All `INFO` fields are required and are included in every `.woz` file.

The output of the `dump` command is designed to by grep-able, if you're into that kind of thing.

```
$ wozardry dump "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
```

will show just the `INFO` section.

**Tip**: [the .woz specification](https://applesaucefdc.com/woz/reference2/) lists the standard metadata fields and the acceptable values of all info fields.

## `edit` command

This command lets you modify any information or metadata field in a `.woz` file. This is where the fun(\*) starts.

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
 
 Working with this same "Wings of Fury" disk image, let's give the game author his due by adding the `developer` metadata field:
 
 ```
 $ wozardry edit -m "developer:Steve Waldo" "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
 ```

Metadata fields are arbitrary; there is a standard set listed in [the .woz specification](https://applesaucefdc.com/woz/reference2/), but you can add your own.

```
$ wozardry edit -m "genre:action" -m "perspective:side view" "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

You can use a similar syntax to remove metadata fields that don't apply to this disk.

```
$ wozardry edit -m "version:" -m "notes:" -m "side_name:" -m "subtitle:" "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

Now let's look at that metadata section again:

```
$ wozardry dump "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz" | grep "^META"
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

You can modify `INFO` fields using a similar syntax (`-i` instead of `-m`), but be aware that `INFO` fields are highly constrained, and incorrect values can have noticeable effects in emulators. `wozardry` will reject any values that are nonsensical or out of range, but even in-range values can render the disk image unbootable. For example, the "optimal bit timing" field specifies the rate at which bits appear in the floppy drive data latch; if the rate is not what the disk's low-level RWTS code is expecting, the disk may be unable to read itself.

Nonetheless, here are some examples of changing `INFO` fields. To tell emulators that a disk is not write-protected, set the `write_protected` field to `no`, `false`, or `0`.

```
$ wozardry edit -i "write_protected:no" "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

To tell emulators that the disk only runs on certain Apple II models, set the `compatible_hardware` field with a pipe-separated list. (Values may appear in any order. See `kRequiresMachine` in the `wozardry` source code for all the acceptable values.)

```
$ wozardry edit -i "compatible_hardware:2e|2e+|2c|2gs" "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
```

### How to convert WOZ1 to WOZ2 files

As of this writing, the `.woz` specification has undergone one major revision, which changed the internal structure of a `.woz` file and added several new `INFO` fields. Both file formats use the `.woz` file extension; they are distinguished by magic bytes (`WOZ1` vs. `WOZ2`) within the file.

Let's say you have an older `WOZ1` file, like this one from the `WOZ 1.0` directory of the official test images collection:

```
$ wozardry dump "woz test images/WOZ 1.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
INFO:  File format version:    1
INFO:  Disk type:              5.25-inch (140K)
INFO:  Write protected:        yes
INFO:  Tracks synchronized:    yes
INFO:  Weakbits cleaned:       yes
INFO:  Creator:                Applesauce v0.29
```

The "file format version" confirms this is a `WOZ1` file. To convert it to a `WOZ2` file, set the `version` field to `2`.

```
$ wozardry -i "version:2" "woz test images/WOZ 1.0/Wings of Fury - Disk 1, Side A.woz"

$ wozardry dump "woz test images/WOZ 1.0/Wings of Fury - Disk 1, Side A.woz" | grep "^INFO"
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

All the new (v2-specific) `INFO` fields are initialized with default values. Existing fields like the write-protected flag are retained. ("Largest track" is a calculated field and can not be set directly.)

## `import` and `export` commands

These commands allow you to access the information and metadata in a `.woz` file in `JSON` format.

```
$ wozardry export "woz test images/WOZ 2.0/Wings of Fury - Disk 1, Side A.woz"
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

You can pipe the output of the `export` command to the `import` command to copy metadata from one `.woz` file to another.

```
$ wozardry export game-side-a.woz | wozardry import game-side-b.woz
```

Technically, this merges metadata. All metadata fields in `game-side-a.woz` will be copied to `game-side-b.woz`, overwriting any existing values for those fields. But if `game-side-b.woz` already had additional metadata fields that were not present in `game-side-a.woz`, those will be retained.

**Tip**: [a2rchery](https://github.com/a2-4am/a2rchery) is a tool to manipulate `.a2r` flux images. These `.a2r` files can also have embedded metadata, just like `.woz` files. And guess what! `a2rchery` also has `import` and `export` commands, just like `wozardry`. You see where this is going.

```
$ wozardry export game.woz | a2rchery import game.a2r
```
