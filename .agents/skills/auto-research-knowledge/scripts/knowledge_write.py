"""Cooperative, optimistic publication of research notes; Python standard library only.

Draft independently, then compare-and-swap under one OS file lock. Never unlink
the lock file: the kernel releases the lock even if the writer is terminated.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

VERSION = 1
RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")


class WriteError(Exception):
    def __init__(self, code, message, **details):
        self.code = code
        self.result = {"status": message, **details}
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def read_optional(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".knowledge-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


class Coordinator:
    def __init__(self, root, timeout=15):
        self.root = Path(root).resolve()
        if not (self.root / "Research_Knowledge").is_dir():
            raise WriteError(2, "invalid_project", root=str(self.root))
        self.state = self.root / "Research_Knowledge" / "_coordination"
        if not self.state.resolve().is_relative_to(self.root):
            raise WriteError(2, "unsafe_state_directory")
        if timeout < 0 or timeout > 60:
            raise WriteError(2, "timeout_must_be_between_0_and_60")
        self.timeout = timeout

    @contextmanager
    def lock(self):
        self.state.mkdir(parents=True, exist_ok=True)
        # This persistent inode/file is shared by all writers. No stale-lock deletion.
        with (self.state / "writer.lock").open("a+b") as f:
            if os.fstat(f.fileno()).st_size == 0:
                f.write(b"0")
                f.flush()
            start = time.monotonic()
            acquired = False
            try:
                while not acquired:
                    try:
                        f.seek(0)
                        if os.name == "nt":
                            import msvcrt
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        acquired = True
                    except OSError as e:
                        if e.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                            raise
                        if time.monotonic() - start >= self.timeout:
                            raise WriteError(4, "busy", retry="retry the same command later")
                        time.sleep(0.05)
                yield
            finally:
                if acquired:
                    f.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def target(self, name):
        name = name.replace("\\", "/")
        bits = name.split("/")
        if any(not p or p in (".", "..") or ":" in p or p.endswith((".", " ")) for p in bits):
            raise WriteError(2, "invalid_target", path=name)
        allowed = name in (".gitignore", "README.md", "AGENTS.md")
        if len(bits) == 2 and bits[0] == "Research_Knowledge":
            allowed = bits[1] in ("INDEX.md", "PROJECT_MAP.md", "DECISIONS.md")
        if len(bits) == 3 and bits[:2] in (["Research_Knowledge", "papers"],
                                          ["Research_Knowledge", "topics"],
                                          ["Research_Knowledge", "questions"]):
            allowed = bits[-1].endswith(".md") and not bits[-1].startswith(".")
        if len(bits) >= 3 and bits[:2] == ["Research_Knowledge", "reproductions"]:
            allowed = (Path(name).suffix.lower() in (".md", ".py", ".r", ".json", ".yaml", ".yml", ".toml", ".txt")
                       and all(not p.startswith((".", "_")) and p.lower() != "local" for p in bits[2:]))
        target = self.root.joinpath(*bits)
        if not allowed or not target.resolve().is_relative_to(self.root):
            raise WriteError(2, "target_not_allowed", path=name)
        # Refuse junctions/symlinks even if their destination happens to be in root.
        cursor = target
        while cursor != self.root:
            if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
                raise WriteError(2, "linked_target_not_allowed", path=name)
            cursor = cursor.parent
        return name, target

    def folder(self, run):
        if not RUN_ID.fullmatch(run):
            raise WriteError(2, "invalid_run_id", run=run)
        path = self.state / "runs" / run
        if not path.resolve().is_relative_to(self.state.resolve()) or path.is_symlink():
            raise WriteError(2, "unsafe_run_directory")
        return path

    def load(self, run):
        path = self.folder(run) / "manifest.json"
        if not path.is_file():
            raise WriteError(2, "unknown_run", run=run)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("version") != VERSION or value.get("run") != run or value.get("root") != str(self.root):
            raise WriteError(2, "invalid_manifest", run=run)
        return value

    def save(self, manifest):
        manifest["updated"] = now()
        save_json(self.folder(manifest["run"]) / "manifest.json", manifest)

    def runs(self):
        directory = self.state / "runs"
        return [self.load(p.name) for p in sorted(directory.iterdir()) if p.is_dir() and RUN_ID.fullmatch(p.name)] if directory.exists() else []

    def require_recovered(self):
        pending = [m["run"] for m in self.runs() if m["state"] in ("applying", "recovery_required")]
        if pending:
            raise WriteError(5, "recovery_required", runs=pending, action="inspect status; recover the interrupted run before publishing")

    def begin(self, owner):
        with self.lock():
            self.require_recovered()
            run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
            manifest = {"version": VERSION, "run": run, "root": str(self.root), "owner": owner,
                        "state": "open", "created": now(), "entries": []}
            self.folder(run).mkdir(parents=True)
            self.save(manifest)
            return {"status": "open", "run": run, "draft_root": str(self.folder(run) / "draft")}

    def checkout(self, run, paths):
        with self.lock():
            self.require_recovered()
            m = self.load(run)
            if m["state"] != "open":
                raise WriteError(2, "run_not_open", run=run, state=m["state"])
            targets = [self.target(p) for p in paths]
            known = {e["path"].casefold() for e in m["entries"]}
            result = []
            for name, target in targets:
                if name.casefold() in known:
                    raise WriteError(2, "already_checked_out", path=name, action="keep the existing draft or start a new run")
                known.add(name.casefold())
            for name, target in targets:
                before = read_optional(target)
                if before is not None:
                    atomic_write(self.folder(run) / "base" / name, before)
                draft = self.folder(run) / "draft" / name
                atomic_write(draft, before if before is not None else b"")
                m["entries"].append({"path": name, "base_sha256": digest(before)})
                result.append({"path": name, "base_sha256": digest(before), "draft": str(draft)})
            self.save(m)
            return {"status": "checked_out", "run": run, "files": result}

    def inspect_changes(self, m):
        changes, conflicts = [], []
        for e in m["entries"]:
            name, target = self.target(e["path"])
            draft = (self.folder(m["run"]) / "draft" / name).read_bytes()
            # Validate text; keep exact source bytes (BOM/newlines) if unchanged.
            draft.decode("utf-8-sig")
            if digest(draft) == e["base_sha256"]:
                continue
            current = read_optional(target)
            if digest(current) != e["base_sha256"]:
                conflicts.append({"path": name, "expected": e["base_sha256"], "actual": digest(current)})
            changes.append({**e, "new_sha256": digest(draft), "data": draft})
        return changes, conflicts

    def check(self, run):
        with self.lock():
            self.require_recovered()
            m = self.load(run)
            if m["state"] == "committed":
                return {"status": "already_committed", "run": run}
            if m["state"] != "open":
                raise WriteError(2, "run_not_open", run=run, state=m["state"])
            changes, conflicts = self.inspect_changes(m)
            if conflicts:
                raise WriteError(3, "conflict", run=run, conflicts=conflicts)
            return {"status": "ready", "run": run, "files": [e["path"] for e in changes]}

    def restore(self, m):
        # Preflight every target before restoring ANY target; preserve unrelated edits.
        for e in m["publication"]:
            _, target = self.target(e["path"])
            actual = digest(read_optional(target))
            if actual not in (e["base_sha256"], e["new_sha256"]):
                raise WriteError(5, "recovery_conflict", run=m["run"], path=e["path"], actual=actual)
            before = read_optional(self.folder(m["run"]) / "base" / e["path"])
            if digest(before) != e["base_sha256"]:
                raise WriteError(5, "invalid_backup", run=m["run"], path=e["path"])
        for e in reversed(m["publication"]):
            _, target = self.target(e["path"])
            if digest(read_optional(target)) == e["base_sha256"]:
                continue
            if e["base_sha256"] is None:
                target.unlink()
            else:
                atomic_write(target, (self.folder(m["run"]) / "base" / e["path"]).read_bytes())

    def commit(self, run):
        with self.lock():
            self.require_recovered()
            m = self.load(run)
            if m["state"] == "committed":
                return {"status": "already_committed", "run": run}
            if m["state"] != "open":
                raise WriteError(2, "run_not_open", run=run, state=m["state"])
            changes, conflicts = self.inspect_changes(m)
            if conflicts:
                for e in conflicts:
                    _, target = self.target(e["path"])
                    current = read_optional(target)
                    if current is not None:
                        atomic_write(self.folder(run) / "conflict" / e["path"], current)
                m["state"], m["conflicts"] = "conflict", conflicts
                self.save(m)
                raise WriteError(3, "conflict", run=run, conflicts=conflicts,
                                 preserved=str(self.folder(run)), action="start a new run; merge base, draft and latest; never force overwrite")
            if not changes:
                return {"status": "no_changes", "run": run}
            # Freeze publication bytes before journaling. User-edited drafts stay intact.
            for e in changes:
                atomic_write(self.folder(run) / "publish" / e["path"], e["data"])
            m["publication"] = [{k: v for k, v in e.items() if k != "data"} for e in changes]
            m["state"] = "applying"
            self.save(m)  # durable intent BEFORE the first formal-file replacement
            try:
                for e in changes:
                    _, target = self.target(e["path"])
                    atomic_write(target, e["data"])
                m["state"] = "committed"
                self.save(m)
            except Exception:
                # If ordinary I/O fails, undo the batch; abrupt termination is handled
                # by recover(), and blocks all later publications in the meantime.
                m["state"] = "recovery_required"
                self.save(m)
                try:
                    self.restore(m)
                    m["state"] = "rolled_back"
                    self.save(m)
                except Exception as recovery_error:
                    raise WriteError(5, "recovery_required", run=run, reason=str(recovery_error))
                raise
            return {"status": "committed", "run": run, "files": [e["path"] for e in changes],
                    "backup_root": str(self.folder(run) / "base")}

    def recover(self, run):
        with self.lock():
            m = self.load(run)
            if m["state"] not in ("applying", "recovery_required"):
                raise WriteError(2, "run_does_not_need_recovery", state=m["state"])
            self.restore(m)
            m["state"] = "rolled_back"
            self.save(m)
            return {"status": "rolled_back", "run": run, "drafts_preserved": str(self.folder(run) / "draft")}

    def status(self):
        with self.lock():
            return {"status": "ok", "root": str(self.root), "runs": [
                {k: m[k] for k in ("run", "owner", "state", "updated")} for m in self.runs()]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root containing Research_Knowledge")
    parser.add_argument("--timeout", type=float, default=15, help="maximum lock wait in seconds (0..60)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("begin").add_argument("--owner", required=True)
    checkout = sub.add_parser("checkout")
    checkout.add_argument("--run", required=True)
    checkout.add_argument("--path", action="append", required=True)
    for command in ("check", "commit", "recover"):
        sub.add_parser(command).add_argument("--run", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    try:
        coordinator = Coordinator(args.root, args.timeout)
        if args.command == "begin":
            result = coordinator.begin(args.owner)
        elif args.command == "checkout":
            result = coordinator.checkout(args.run, args.path)
        elif args.command == "status":
            result = coordinator.status()
        else:
            result = getattr(coordinator, args.command)(args.run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except WriteError as e:
        print(json.dumps(e.result, ensure_ascii=False, indent=2))
        return e.code
    except (OSError, ValueError, KeyError) as e:
        print(json.dumps({"status": "error", "type": type(e).__name__, "message": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
