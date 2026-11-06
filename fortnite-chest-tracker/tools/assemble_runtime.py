import gzip
import io
import os
import shutil
import sys
import tarfile
import zipfile

src = sys.argv[1] if len(sys.argv) > 1 else ""
dest = sys.argv[2] if len(sys.argv) > 2 else ""


def is_wheel(path):
    return zipfile.is_zipfile(path)


def unpack_wheel(path, target):
    os.makedirs(target, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            out = os.path.join(target, info.filename)
            try:
                if info.is_dir():
                    os.makedirs(out, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with zf.open(info) as s, open(out, "wb") as d:
                        while True:
                            chunk = s.read(1 << 20)
                            if not chunk:
                                break
                            d.write(chunk)
            except OSError as e:
                print("FAIL", info.filename, e)


def is_targz(path):
    try:
        with open(path, "rb") as f:
            return gzip.decompress(f.read(2)) if False else f.read(2) == b"\x1f\x8b"
    except OSError:
        return False


def unpack_targz(path, target):
    with tarfile.open(path) as tf:
        for m in tf.getmembers():
            out = os.path.join(target, m.name)
            if m.isdir():
                os.makedirs(out, exist_ok=True)
            elif m.isfile():
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with tf.extractfile(m) as s, open(out, "wb") as d:
                    shutil.copyfileobj(s, d)


def copy_tree(s, d):
    os.makedirs(d, exist_ok=True)
    for name in os.listdir(s):
        a, b = os.path.join(s, name), os.path.join(d, name)
        if os.path.isdir(a):
            copy_tree(a, b)
        else:
            try:
                shutil.copy2(a, b)
            except OSError as e:
                print("FAIL copy", a, e)


def main():
    if not src or not dest:
        print("usage: assemble_runtime.py <folder with python.tar.gz + *.whl> <runtime dir>")
        return 2
    os.makedirs(dest, exist_ok=True)
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if os.path.isdir(path):
            if is_wheel(path):
                unpack_wheel(path, os.path.join(dest, name.split("-")[0]))
            else:
                copy_tree(path, os.path.join(dest, name))
        elif name.endswith(".whl"):
            unpack_wheel(path, dest)
        elif name.endswith(".tar.gz") or is_targz(path):
            unpack_targz(path, dest)
        else:
            shutil.copy2(path, os.path.join(dest, name))
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
