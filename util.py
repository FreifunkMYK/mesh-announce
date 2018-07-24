import os

def source_dirs(dir):
    dirs = next(os.walk(dir))[1]
    return filter(lambda d: not d.startswith('__'), dirs)

def modules(dir):
    return [os.path.splitext(f)[0] for f in next(os.walk(dir))[2]
        if f.endswith('.py') and not f.startswith('__')]

def find_modules(base, *path):
    path_files = []
    dir_abs = base
    dir_abs = os.path.join(base, *path)
    dirs = source_dirs(dir_abs)
    for dir in dirs:
        # Ugly hack because python < 3.5 does not support arguments after asterisk expression
        path_files += find_modules(base, *(list(path) + [dir]))

    files = list(modules(dir_abs))
    if len(files) > 0:
        lpath = list(map(os.path.basename, path))
        path_files.append((lpath, files))
    return path_files

