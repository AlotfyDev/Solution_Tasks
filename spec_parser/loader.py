import glob
import os
import codecs


def load_file(filepath: str) -> dict:
    with codecs.open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return {
        "path": os.path.normpath(filepath),
        "filename": os.path.basename(filepath),
        "content": content,
    }


def load_directory(dirpath: str, pattern: str = "*.md") -> list[dict]:
    files = sorted(glob.glob(os.path.join(dirpath, pattern)))
    return [load_file(f) for f in files]
