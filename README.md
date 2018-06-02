```
$ ./wozardry verify -h
usage: wozardry verify [-h] file

Verify file structure and metadata of a .woz disk image (produces no output
unless a problem is found)

positional arguments:
  file        .woz disk image

optional arguments:
  -h, --help  show this help message and exit



$ ./wozardry dump -h
usage: wozardry dump [-h] file

Print all available information and metadata in a .woz disk image

positional arguments:
  file        .woz disk image

optional arguments:
  -h, --help  show this help message and exit



$ ./wozardry edit -h
usage: wozardry edit [-h] [-i INFO] [-m META] file

Edit information and metadata in a .woz disk image

positional arguments:
  file                  .woz disk image (modified in place)

optional arguments:
  -h, --help            show this help message and exit
  -i INFO, --info INFO  change information field. INFO format is "key:value".
                        Acceptable keys are disk_type, write_protected,
                        synchronized, cleaned, creator, version. Other keys
                        are ignored.
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
