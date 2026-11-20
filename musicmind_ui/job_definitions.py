"""Shared job labels and groups for UI state and page rendering."""

JOB_LABELS = [("plex_history", "Sync Plex listening history"), ("fullsync", "Full Sync"), ("ingest", "Sync Plex Library"),
              ("lastfm", "Sync Last.fm"), ("tagger", "Tag tracks"),
              ("context", "Listening context"), ("mbenrich", "MusicBrainz enrichment"),
              ("aienrich", "AI enrichment"), ("gaps", "Find collection gaps"),
              ("fingerprint", "Fingerprint tracks"), ("copyforward", "Copy forward analysis"),
              ("dedup", "Duplicate report"), ("varesolve", "Resolve Various Artists"),
              ("recordingmbid", "Resolve recording IDs"), ("synapse", "Synapse analysis")]



JOB_GROUPS = [
    ("Library", "Run individual library and listening-history updates.", [
        ("ingest", "Sync Plex library", "Imports Plex's current library into MusicMind's local index."),
        ("plex_history", "Sync Plex listening history", "Imports dated music plays retained by Plex for the server owner."),
        ("lastfm", "Sync Last.fm", "Updates listening history and recent play counts."),
    ]),
    ("Enrichment", "Add descriptive metadata used by search, charts, and playlist matching.", [
        ("mbenrich", "MusicBrainz enrichment", "Matches artists to verified MusicBrainz records."),
        ("aienrich", "AI enrichment", "Fills remaining artist and track metadata."),
        ("tagger", "Tag tracks", "Generates specific genre and mood tags for tracks."),
        ("context", "Listening context", "Adds context signals to Last.fm listening history."),
        ("recordingmbid", "Resolve recording IDs", "Matches tracks to MusicBrainz recording IDs."),
    ]),
    ("Analysis", "Run audio and collection analysis used by insights and recommendations.", [
        ("gaps", "Find collection gaps", "Finds frequently played artists missing from Plex."),
        ("fingerprint", "Fingerprint tracks", "Identifies recordings from their audio fingerprints."),
        ("copyforward", "Copy forward analysis", "Reuses valid analysis for matching tracks."),
    ]),
    ("Maintenance", "Review duplicates and clean up artist identities.", [
        ("dedup", "Duplicate report", "Finds likely duplicate tracks and albums."),
        ("varesolve", "Resolve Various Artists", "Repairs compilation artist attribution."),
    ]),
]




def _job_label(name: str) -> str:
    labels = dict(JOB_LABELS)
    labels["synapse_full"] = "Synapse audio analysis"
    labels["synapse_limited"] = "Limited Synapse analysis"
    labels["synapse_count"] = "Synapse track count"
    labels["synapse_estimate"] = "Synapse time estimate"
    return labels.get(name, name.replace("_", " ").title())

