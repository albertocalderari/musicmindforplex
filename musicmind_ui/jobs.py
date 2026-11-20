"""Detached jobs used by the Reflex interface.

The PID and output live on disk so a web worker restart does not erase the
observable state of a process that is still running.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from musicmind.commands import MODULES
from musicmind.paths import PROJECT_ROOT


JOB_DIR = PROJECT_ROOT / "job_logs"
COMMANDS = {
    "plex_history": "plex_history.py",
    "ingest": "ingest.py",
    "lastfm": "sync.py",
    "tagger": "tag_tracks.py",
    "context": "listening_context.py",
    "mbenrich": "mb_enrich_artists.py",
    "aienrich": "enrich_artists.py",
    "gaps": "gaps.py",
    "fingerprint": "fingerprint_tracks.py",
    "copyforward": "copy_forward_analysis.py",
    "dedup": "dedup_report.py",
    "varesolve": "va_resolve.py",
    "recordingmbid": "resolve_recording_mbids.py",
    "synapse": "synapse_analyze.py",
}
TEST_COMMANDS = {
    "mb_dry_run": ("mb_enrich_artists.py", ["--test", "--limit", "3"]),
    "mb_limited_run": ("mb_enrich_artists.py", ["--limit", "1"]),
    "ai_dry_run": ("enrich_artists.py", ["--test", "--limit", "3"]),
    "ai_limited_run": ("enrich_artists.py", ["--limit", "1"]),
}
GROUP_COMMANDS = {
    "group_library": ("ingest", "plex_history", "lastfm"),
    "group_enrichment": ("mbenrich", "aienrich", "tagger", "context", "recordingmbid"),
    "group_analysis": ("gaps", "fingerprint", "copyforward"),
    "group_maintenance": ("dedup", "varesolve"),
}
FULLSYNC_CHILD_JOBS = {
    "plex_history", "ingest", "fingerprint", "copyforward", "varesolve", "recordingmbid",
    "lastfm", "mbenrich", "aienrich", "tagger", "synapse", "synapse_full",
    "synapse_limited",
}

FULLSYNC_PHASES = [
    ("plex_scan", "🔍 Triggering Plex library scan...", "Scanning Plex library"),
    ("ingest", "🔄 Syncing Plex Library...", "Syncing Plex library"),
    ("fingerprint", "🔗 Fingerprinting new tracks...", "Fingerprinting new tracks"),
    ("copy_forward", "♻️ Checking for known duplicates...", "Copying prior analysis"),
    ("va_resolve", "🎭 Resolving Various Artists tracks...", "Resolving compilation artists"),
    ("enrich_compilations", "🏷️ Enriching compilations (ID3 fallback)...", "Enriching compilations"),
    ("recording_mbids", "🎼 Resolving recording IDs...", "Resolving recording IDs"),
    ("lastfm", "🎵 Syncing Last.fm...", "Syncing Last.fm"),
    ("mb_enrich", "🔍 Enriching artists (MusicBrainz)...", "Enriching artists with MusicBrainz"),
    ("ai_enrich", "🤖 Enriching artists (AI fallback)...", "Enriching artists with AI"),
    ("tag_tracks", "🏷️ Tagging new tracks...", "Tagging tracks"),
    ("synapse", "🧠 Analyzing audio (Synapse: BPM/key/danceability)...", "Analyzing audio"),
]


def group_tasks(name: str) -> tuple[str, ...]:
    tasks = GROUP_COMMANDS[name]
    if name == "group_library":
        try:
            from config import LASTFM_KEY
        except ImportError:
            LASTFM_KEY = ""
        if not LASTFM_KEY:
            return tuple(task for task in tasks if task != "lastfm")
    return tasks


def _paths(name: str) -> tuple[Path, Path]:
    if name not in {*COMMANDS, *TEST_COMMANDS, *GROUP_COMMANDS, "fullsync", "synapse_full",
                    "synapse_count", "synapse_estimate", "synapse_limited", "resync"}:
        raise ValueError("Unknown job")
    JOB_DIR.mkdir(exist_ok=True)
    return JOB_DIR / f"{name}.json", JOB_DIR / f"{name}.log"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def _tail_log(path: Path, limit: int = 120) -> list[str]:
    """Read only the end of a potentially long running job log."""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()
        chunk = b""
        while position > 0 and chunk.count(b"\n") <= limit:
            size = min(8192, position)
            position -= size
            f.seek(position)
            chunk = f.read(size) + chunk
    return chunk.decode("utf-8", errors="replace").splitlines(keepends=True)[-limit:]


def status(name: str) -> dict:
    meta_path, log_path = _paths(name)
    if name == "fullsync":
        log_path = PROJECT_ROOT / "fullsync_live.log"
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, ValueError):
        meta = {}
    pid = int(meta.get("pid", 0))
    try:
        lines = _tail_log(log_path)
    except OSError:
        lines = []
    result = {"name": name, "running": bool(pid and not meta.get("finished") and _alive(pid)),
              "exit_code": meta.get("exit_code"), "stopped": meta.get("stopped", False),
              "log": "".join(lines)}
    if name == "fullsync":
        try:
            progress_state = json.loads((JOB_DIR / "fullsync_progress.json").read_text())
        except (OSError, ValueError):
            progress_state = {}
        if progress_state:
            active = progress_state.get("active", [])
            stage_labels = {stage_id: label for stage_id, _, label in FULLSYNC_PHASES}
            if len(active) > 1:
                phase = f"{len(active)} stages running in parallel"
            elif active:
                phase = stage_labels.get(active[-1], progress_state.get("phase", "Running"))
            else:
                phase = progress_state.get("phase", "Waiting to start")
            if result["stopped"]:
                phase = f"Stopped · {phase}"
            elif not result["running"] and not progress_state.get("finished"):
                phase = f"Interrupted · {phase}"
            result.update(phase=phase,
                          progress=progress_state.get("progress", 0),
                          step=progress_state.get("step", 0))
        else:
            result.update(phase="Waiting to start", progress=0, step=0)
    return result


def stop(name: str) -> dict:
    meta_path, _ = _paths(name)
    try:
        meta = json.loads(meta_path.read_text())
        pid = int(meta["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(f"{name} is not running")
    if meta.get("finished") or not _alive(pid):
        raise ValueError(f"{name} is not running")
    command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True).strip()
    if f"musicmind_ui.jobs run {name}" not in command:
        raise ValueError("Job process could not be verified")
    os.killpg(pid, signal.SIGTERM)
    meta["finished"] = True
    meta["stopped"] = True
    meta["exit_code"] = 143
    temp_path = meta_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(meta))
    os.replace(temp_path, meta_path)
    return status(name)


def start(name: str, args: list[str] | None = None) -> dict:
    meta_path, log_path = _paths(name)
    current = status(name)
    if current["running"]:
        raise ValueError(f"{name} is already running")
    fullsync_running = status("fullsync")["running"] if name != "fullsync" else False
    requested_jobs = group_tasks(name) if name in GROUP_COMMANDS else (name,)
    overlap = set(requested_jobs) & FULLSYNC_CHILD_JOBS
    if name == "fullsync":
        active = {job for job in FULLSYNC_CHILD_JOBS if status(job)["running"]}
        active.update(
            group for group in GROUP_COMMANDS
            if set(group_tasks(group)) & FULLSYNC_CHILD_JOBS and status(group)["running"]
        )
        if active:
            raise ValueError(f"Cannot start full sync while {', '.join(sorted(active))} is running")
    elif fullsync_running and overlap:
        raise ValueError(f"Cannot start {name} while full sync is running")
    if name in GROUP_COMMANDS:
        active = [task for task in group_tasks(name) if status(task)["running"]]
        if active:
            raise ValueError(f"Cannot start {name} while {', '.join(active)} is running")
    else:
        active_groups = [group for group in GROUP_COMMANDS
                         if name in group_tasks(group) and status(group)["running"]]
        if active_groups:
            raise ValueError(f"Cannot start {name} while {', '.join(active_groups)} is running")
    args = args or []
    if name == "synapse_limited":
        if len(args) != 1 or not args[0].isdigit() or not 1 <= int(args[0]) <= 500:
            raise ValueError("Limit must be between 1 and 500")
    elif name == "resync":
        if len(args) not in (2, 3) or not args[0].strip() or not args[1].strip() or (len(args) == 3 and args[2] != "--run"):
            raise ValueError("Artist and album are required")
    elif args:
        raise ValueError("Unexpected job arguments")
    command = [sys.executable, "-u", "-m", "musicmind_ui.jobs", "run", name, *args]
    if name == "fullsync":
        (JOB_DIR / "fullsync_progress.json").write_text(json.dumps({
            "phase": "Starting Plex scan", "step": 0, "progress": 0,
            "total": len(FULLSYNC_PHASES), "finished": False, "active": [],
        }))
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    meta_path.write_text(json.dumps({"pid": proc.pid, "command": name, "finished": False}))
    return status(name)


def _run_one(name: str, args: list[str]) -> int:
    if name == "fullsync":
        from web.app import _run_fullsync_pipeline, FULLSYNC_LOG_PATH

        _run_fullsync_pipeline()
        return 0 if "✅ Full sync complete." in Path(FULLSYNC_LOG_PATH).read_text(errors="replace") else 1
    if name in TEST_COMMANDS:
        module_name, command_args = TEST_COMMANDS[name]
    elif name.startswith("synapse_"):
        module_name = COMMANDS["synapse"]
        command_args = {"synapse_full": [], "synapse_count": ["--count"],
                        "synapse_estimate": ["--estimate"],
                        "synapse_limited": ["--limit", *args]}[name]
    elif name == "resync":
        module_name, command_args = "resync_item.py", ["--artist", args[0], "--album", args[1], *args[2:]]
    else:
        module_name, command_args = COMMANDS[name], []
    module = MODULES[module_name]
    return subprocess.call([sys.executable, "-u", "-m", module, *command_args], cwd=PROJECT_ROOT)


def run(name: str, args: list[str]) -> int:
    meta_path, _ = _paths(name)
    for _ in range(50):
        try:
            if json.loads(meta_path.read_text()).get("pid") == os.getpid():
                break
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    try:
        if name in GROUP_COMMANDS:
            failures = []
            for task in group_tasks(name):
                print(f"\n=== Starting {task} ===", flush=True)
                try:
                    task_code = _run_one(task, [])
                except Exception as exc:
                    print(f"{task} failed: {exc}", flush=True)
                    task_code = 1
                print(f"=== {task} finished (exit {task_code}) ===", flush=True)
                if task_code:
                    failures.append(task)
            if failures:
                print(f"Section finished with failures: {', '.join(failures)}", flush=True)
            code = 1 if failures else 0
        else:
            code = _run_one(name, args)
    except Exception as exc:
        print(f"Job failed: {exc}", flush=True)
        code = 1
    # Atomic replacement prevents readers observing a partial metadata file.
    meta = {"pid": os.getpid(), "command": name, "finished": True, "exit_code": code}
    temp_path = meta_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(meta))
    os.replace(temp_path, meta_path)
    return code


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] == "run":
    sys.exit(run(sys.argv[2], sys.argv[3:]))
