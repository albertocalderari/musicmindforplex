# TODO

- [ ] Replace detached job subprocesses with a durable worker queue.
  - Store job state, progress, and checkpoints in SQLite; have the UI enqueue work and read status.
  - Run the worker as a separate systemd service or Docker process, with automatic restart and recovery after process or machine restarts.
  - Start with MusicBrainz enrichment, resuming from artists not yet enriched, then migrate the other long-running jobs.
  - Prevent duplicate workers from claiming the same job and retain useful per-job logs and failure status.
