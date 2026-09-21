"""Check pinned source contents, ignoring platform-specific uid/gid/mode/mtime."""
import hashlib
from pathlib import Path, PurePosixPath
import sys
import tarfile


def verify(archive, directory):
    root = Path(directory).resolve()
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts:
                raise ValueError('Unsafe archive path')
            target = root.joinpath(*name.parts)
            if not target.resolve().is_relative_to(root):
                raise ValueError('Source path escapes its directory')
            if member.isdir():
                if not target.is_dir():
                    raise ValueError('Missing directory: ' + member.name)
            elif member.isfile():
                if target.is_symlink() or not target.is_file():
                    raise ValueError('Missing or replaced file: ' + member.name)
                expected = hashlib.sha256(source.extractfile(member).read()).digest()
                if hashlib.sha256(target.read_bytes()).digest() != expected:
                    raise ValueError('Modified source: ' + member.name)
            elif member.issym():
                if not target.is_symlink() or str(target.readlink()) != member.linkname:
                    raise ValueError('Modified link: ' + member.name)
            else:
                raise ValueError('Unsupported archive entry: ' + member.name)


if __name__ == '__main__':
    verify(sys.argv[1], sys.argv[2])
