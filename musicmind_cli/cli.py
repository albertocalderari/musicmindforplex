"""Command-line entry point for local MusicMind tasks."""

import argparse
import sqlite3
import os
import shutil
import subprocess
import sys
from pathlib import Path



def main(argv=None):
    # Installed console scripts start in the virtualenv's bin directory.
    # Prefer the current directory when it contains the user's config.py.
    package_root = Path(__file__).resolve().parent.parent
    config_root = Path.cwd() if (Path.cwd() / "config.py").is_file() else package_root
    sys.path.insert(0, str(config_root))

    parser = argparse.ArgumentParser(prog="musicmind")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="start the web server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--production", action="store_true",
                       help="serve a fixed production build without auto reload")

    database = commands.add_parser("db", help="database commands")
    database_commands = database.add_subparsers(dest="db_command", required=True)
    database_commands.add_parser("init", help="create or update the local schema")

    commands.add_parser("ingest", help="import tracks from Plex")

    args = parser.parse_args(argv)
    if args.command == "serve":
        env = os.environ.copy()
        env.setdefault("REFLEX_USE_NPM", "1")
        node_bin = shutil.which("node", path=env.get("PATH"))
        if node_bin:
            version = subprocess.check_output(
                [node_bin, "-p", "process.versions.node"], text=True
            ).strip()
            if tuple(int(part) for part in version.split(".")[:3]) >= (22, 22, 0):
                env["PATH"] = f"{Path(node_bin).parent}{os.pathsep}{env.get('PATH', '')}"
        mode = "prod" if args.production else "dev"
        backend_port = args.port if args.production else args.port + 1
        raise SystemExit(subprocess.call(
            [sys.executable, "-m", "reflex", "run", "--env", mode,
             "--frontend-port", str(args.port), "--backend-port", str(backend_port),
             "--backend-host", args.host],
            cwd=config_root, env=env,
        ))
    elif args.command == "db":
        from config import DB_PATH
        from musicmind.db.schema import init_all

        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            init_all(conn)
        finally:
            conn.close()
    elif args.command == "ingest":
        from musicmind.ingest import main as ingest_main

        ingest_main()
