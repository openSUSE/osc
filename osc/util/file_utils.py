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


def merge_configs(src, dest, sections_to_ignore=()):
    import subprocess

    src_gitconfig_lines = subprocess.check_output(["git", "config", "--file", src, "--list"], encoding="utf-8").splitlines()

    for line in src_gitconfig_lines:
        key, value = line.split("=", 1)

        section = key.split(".", 1)[0]
        if section in sections_to_ignore:
            continue

        subprocess.run(["git", "config", "--file", dest, key, value])
