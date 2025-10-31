def merge_files_by_prefix(src, dest):

    with open(dest, "r+") as dest_file:
        dest_dict = dict()
        for line in dest_file:
            key = line.split(maxsplit=2)[0]
            dest_dict[key] = 1

        with open(src) as src_file:
            for line in src_file:
                key = line.split(maxsplit=2)[0]
                if key in dest_dict:
                    pass
                else:
                    dest_file.write(line)


def merge_configs(src, dest, sections_to_ignore=[]):
    import configparser

    src_obj = configparser.ConfigParser(interpolation=None)
    src_obj.read(src)

    for section in sections_to_ignore:
        src_obj.pop(section)

    dest_obj = configparser.ConfigParser(interpolation=None)
    dest_obj.read(dest)

    dest_obj.read_dict(src_obj)

    with open(dest, "w") as dest_file:
        dest_obj.write(dest_file)
