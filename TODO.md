# TODO

- [ ] Replace detached job subprocesses with a durable worker queue.
  - [ ] Store job state, progress, and checkpoints in SQLite; have the UI enqueue work and read status.
  - [ ] Run the worker as a separate systemd service or Docker process, with automatic restart and recovery after process or machine restarts.
  - [ ] Start with MusicBrainz enrichment, resuming from artists not yet enriched, then migrate the other long-running jobs.
  - [ ] Prevent duplicate workers from claiming the same job and retain useful per-job logs and failure status.
  - [ ] fix  MLIR V1 optimization pass is not enabled WARNING: All log messages before absl::InitializeLog() is called are written to STDERR
  - [ ] Fix mobile login requiring users to sign in twice.
  - [ ] Fix mobile redirect opening the web app instead of Plexamp.
  - [ ] Add a music recommender that runs daily.
  - [ ] Make Last.fm sync automatic so it does not need manual triggering.
  - [ ] Move job execution away from subprocesses.
  - [ ] Add an option to run jobs as Kubernetes workloads, similar to the Airflow Kubernetes Executor.
