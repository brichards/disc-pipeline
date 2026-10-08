"""Sort the titles of a disc from their metadata, before the rip.

disc-rip records the triage in the manifest, and holds a decoy disc for review.
disc-identify names the titles after the rip.
"""

from . import config

FEATURE = "feature"
EXTRA = "extra"
UNKNOWN = "unknown"


def classify(title, longest_seconds):
    if title.seconds >= config.FEATURE_MIN_SECONDS and title.chapters >= 12:
        return FEATURE
    if title.seconds >= 0.9 * longest_seconds and longest_seconds > 0:
        return FEATURE
    if title.chapters <= 2 and len(title.audio) <= 1:
        return EXTRA
    if title.seconds < config.FEATURE_MIN_SECONDS:
        return EXTRA
    return UNKNOWN


def decoy_cluster(titles):
    """A decoy disc has many versions of the feature.

    Each version adds different short segments from one set of segments. The
    versions have almost the same duration, size and stream layout, so the
    metadata cannot identify the correct one. Their chapter counts differ,
    because each added segment moves the chapter marks.
    """
    if not titles:
        return []
    longest = max(titles, key=lambda t: t.seconds)
    if longest.seconds < config.FEATURE_MIN_SECONDS:
        return []

    low = longest.seconds * (1 - config.DECOY_DURATION_TOLERANCE)
    high = longest.seconds * (1 + config.DECOY_DURATION_TOLERANCE)
    pool = set(longest.segments)

    cluster = []
    for title in titles:
        if not low <= title.seconds <= high:
            continue
        segments = set(title.segments)
        if pool and segments:
            shared = len(segments & pool) / len(segments)
            if shared < config.DECOY_SEGMENT_OVERLAP:
                continue
        cluster.append(title)
    return cluster


def segment_order_consistency(titles):
    """The versions on a decoy disc keep the segments of one order.

    Each version uses a subset of the segments, in the same order. A disc that
    only has several long titles does not show this pattern.
    """
    import itertools

    agree = disagree = 0
    votes = {}
    for title in titles:
        position = {seg: i for i, seg in enumerate(title.segments)}
        for a, b in itertools.combinations(sorted(position), 2):
            order = position[a] < position[b]
            if (a, b) in votes:
                if votes[(a, b)] == order:
                    agree += 1
                else:
                    disagree += 1
            else:
                votes[(a, b)] = order
    total = agree + disagree
    return 1.0 if total == 0 else agree / total


def select_feature(titles, expected_seconds=None):
    candidates = [t for t in titles if t.seconds >= config.FEATURE_MIN_SECONDS]
    if not candidates:
        return None

    if expected_seconds:
        scored = sorted(candidates, key=lambda t: abs(t.seconds - expected_seconds))
        best = scored[0]
        if abs(best.seconds - expected_seconds) <= 90:
            runners = [t for t in scored[1:] if abs(t.seconds - expected_seconds) <= 90]
            if not runners:
                return best
        return None

    longest = max(candidates, key=lambda t: t.seconds)
    others = [t for t in candidates if t is not longest]
    if any(t.seconds >= 0.95 * longest.seconds for t in others):
        return None
    return longest


def summarize(titles, min_length):
    keep = [t for t in titles if t.seconds >= min_length]
    longest = max((t.seconds for t in keep), default=0)
    cluster = decoy_cluster(keep)

    return {
        "titles_seen": len(titles),
        "titles_over_minimum": len(keep),
        "longest_seconds": longest,
        "decoy_cluster_size": len(cluster),
        "obfuscated": len(cluster) > config.DECOY_CLUSTER_THRESHOLD,
        "segment_order_consistency": (
            round(segment_order_consistency(cluster), 4) if cluster else None
        ),
        "classifications": {
            str(t.index): classify(t, longest) for t in keep
        },
    }
