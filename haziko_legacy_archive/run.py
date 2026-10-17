"""One-shot, allowlisted local Ziko 0.2.4 source archive/retire job."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile

SOURCE = Path("/local_apps/ziko_ai")
OUT = Path("/share/ziko_legacy_archives")
TAR = OUT / "ziko_024_source.tar.gz"
MANIFEST = OUT / "ziko_024_source.manifest.json"
OPTIONS = Path("/data/options.json")
MAX_FILES, MAX_BYTES = 2000, 100 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for block in iter(lambda: fp.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def verified_source():
    if SOURCE.is_symlink() or not SOURCE.is_dir() or SOURCE.is_mount():
        raise ValueError("Expected real legacy source folder is missing")
    config = SOURCE / "config.yaml"
    if config.is_symlink() or not config.is_file() or config.stat().st_size > 8192:
        raise ValueError("Legacy addon config missing or invalid")
    text = config.read_text(encoding="utf-8")
    slugs = re.findall(r'^\s*slug:\s*["\x27]?([a-z0-9_]+)["\x27]?\s*(?:#.*)?$', text, re.M)
    versions = re.findall(r'^\s*version:\s*["\x27]?([0-9.]+)["\x27]?\s*(?:#.*)?$', text, re.M)
    if slugs != ["ziko_ai"] or versions != ["0.2.4"]:
        raise ValueError("Source is not exactly the legacy Ziko 0.2.4")
    files, dirs, total = [], [], 0
    for root, subdirs, names in os.walk(SOURCE, followlinks=False):
        for name in subdirs:
            p = Path(root) / name
            if p.is_symlink() or p.is_mount() or not p.is_dir():
                raise ValueError("Unsafe nested folder")
            dirs.append(str(p.relative_to(SOURCE)))
        for name in names:
            p = Path(root) / name
            if p.is_symlink() or not stat.S_ISREG(p.lstat().st_mode):
                raise ValueError("Unsafe nested source file")
            size = p.stat().st_size
            total += size
            files.append({"path": str(p.relative_to(SOURCE)), "size": size, "sha256": sha256(p)})
            if len(files) > MAX_FILES or total > MAX_BYTES:
                raise ValueError("Source exceeds safety limits")
    return {"version": "0.2.4", "files": sorted(files, key=lambda x: x["path"]),
            "dirs": sorted(dirs), "total_bytes": total}


def verify_tar(data):
    expected = {x["path"]: x for x in data["files"]}
    directories = set(data["dirs"])
    observed, seen_dirs = {}, set()
    with tarfile.open(TAR, "r:gz") as archive:
        for member in archive:
            if not member.name.startswith("ziko_ai/"):
                raise ValueError("Archive contains unexpected path")
            relative = member.name[len("ziko_ai/"):].rstrip("/")
            if member.isdir():
                if relative not in directories:
                    raise ValueError("Unexpected archived directory")
                seen_dirs.add(relative)
            elif member.isfile() and relative in expected and relative not in observed:
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Unreadable archive content")
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(65536), b""):
                    h.update(block)
                observed[relative] = {"path": relative, "size": member.size, "sha256": h.hexdigest()}
            else:
                raise ValueError("Unexpected archived file or link")
    if observed != expected or seen_dirs != directories:
        raise ValueError("Archive verification mismatch")


def archive_only():
    data = verified_source()
    if TAR.exists() or MANIFEST.exists():
        raise ValueError("Prior archive exists; refusing overwrite")
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(OUT, 0o700)
    temporary = OUT / "ziko_024_source.tar.gz.partial"
    if temporary.exists():
        raise ValueError("Prior partial archive exists; investigate before retry")
    try:
        with open(temporary, "xb") as output:
            os.chmod(temporary, 0o600)
            with tarfile.open(mode="w:gz", fileobj=output) as archive:
                for directory in data["dirs"]:
                    archive.add(SOURCE / directory, arcname="ziko_ai/" + directory, recursive=False)
                for item in data["files"]:
                    archive.add(SOURCE / item["path"], arcname="ziko_ai/" + item["path"], recursive=False)
            output.flush()
            os.fsync(output.fileno())
        if verified_source() != data:
            raise ValueError("Source changed during backup")
        os.replace(temporary, TAR)
        verify_tar(data)
        data["archive_sha256"] = sha256(TAR)
        temp_manifest = MANIFEST.with_suffix(".json.partial")
        with open(temp_manifest, "x", encoding="utf-8") as fp:
            os.chmod(temp_manifest, 0o600)
            json.dump(data, fp, ensure_ascii=False, sort_keys=True)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_manifest, MANIFEST)
        print(json.dumps({"status": "archived_and_verified",
                          "files": len(data["files"]), "bytes": data["total_bytes"],
                          "archive": str(TAR)}), flush=True)
    finally:
        if temporary.exists():
            temporary.unlink()


def retire_verified():
    data = verified_source()
    if not MANIFEST.is_file() or not TAR.is_file():
        raise ValueError("No verified source backup; refusing retirement")
    old = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if old.get("archive_sha256") != sha256(TAR):
        raise ValueError("Archive checksum mismatch")
    snapshot = {k: v for k, v in old.items() if k != "archive_sha256"}
    if snapshot != data:
        raise ValueError("Source changed since archival")
    verify_tar(snapshot)
    if verified_source() != snapshot:
        raise ValueError("Source changed before retirement")
    shutil.rmtree(SOURCE)
    print(json.dumps({"status": "retired_legacy_source", "archive": str(TAR),
                      "removed_source": str(SOURCE)}), flush=True)


if __name__ == "__main__":
    mode = json.loads(OPTIONS.read_text(encoding="utf-8")).get("mode", "archive")
    if mode == "archive":
        archive_only()
    elif mode == "retire":
        retire_verified()
    else:
        raise ValueError("Unsupported maintenance mode")
