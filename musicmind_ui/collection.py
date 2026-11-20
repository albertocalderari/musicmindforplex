"""Presentation data for collection statistics, without inferring sync coverage."""
from datetime import datetime


def ranked_rows(rows: list[dict], label: str, value: str) -> list[dict]:
    maximum = max((int(row.get(value) or 0) for row in rows), default=0)
    return [dict(name=str(row.get(label) or "Unclassified"), count=f"{int(row.get(value) or 0):,}",
                 rank=index + 1, width=f"{int(row.get(value) or 0) / maximum * 100 if maximum else 0:.2f}%")
            for index, row in enumerate(rows)]


def timeline_rows(rows: list[dict], granularity: str) -> list[dict]:
    """Insert gaps as unknown observations, never confirmed zero plays."""
    if not rows:
        return []
    values = {str(row[granularity]): int(row['plays']) for row in rows if row.get(granularity)}
    if not values:
        return []
    start, end = min(values), max(values)
    year, month = (int(start[:4]), int(start[5:7])) if granularity == 'month' else (int(start), 1)
    result = []
    while True:
        period = f'{year:04d}-{month:02d}' if granularity == 'month' else f'{year:04d}'
        if period > end:
            break
        plays = values.get(period)
        result.append({'period': period, 'label': datetime(year, month, 1).strftime('%B %Y')
                       if granularity == 'month' else period,
                       'plays': plays, 'period_plays': plays,
                       'display': f'{plays:,}' if plays is not None else 'No recorded data',
                       'period_display': f'{plays:,}' if plays is not None else 'No recorded data'})
        if granularity == 'month' and month < 12:
            month += 1
        else:
            year, month = year + 1, 1
    return result


def combined_timeline_rows(rows: list[dict], granularity: str) -> list[dict]:
    """Per-period totals and labelled contributions, never running totals."""
    result = timeline_rows(rows, granularity)
    by_period = {str(row[granularity]): row for row in rows}
    for row in result:
        recorded = by_period.get(row['period'])
        for source in ('lastfm', 'plex', 'itunes'):
            count = int(recorded.get(source, 0)) if recorded is not None else None
            row[source] = count
            row[f'{source}_display'] = f'{count:,}' if count is not None else '—'
    return result
