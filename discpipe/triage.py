"""Deciding what a disc's titles are, before anything is ripped.

Triage is deliberately conservative. It sorts titles into "probably the
feature", "probably an extra", and "cannot tell" -- the last of which means a
human looks. Actual naming happens after the rip, from title cards and
runtimes, because none of that is visible here.
"""

from . import config

FEATURE = "feature"
EXTRA = "extra"
UNKNOWN = "unknown"


def classify(title, longest_seconds):
    """A first guess from metadata alone.

    Features run long, carry many chapters, and ship several audio tracks.
    Extras are short, have one or two chapters, and usually one stereo track.
    Neither test is trusted later -- disc-identify checks the actual content.
    """
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
    """Titles that are near-duplicates of the longest one.

    Playlist obfuscation authors dozens of variants of the feature that differ
    only in which short alternate segments they splice in. They are
    near-identical in duration and size, and on the discs seen so far
    byte-identical in stream layout, so no amount of metadata picks the real
    one.

    Two things this deliberately does not do. It does not require a matching
    chapter count: on RED 2 the variants split 18/19/17, because including or
    omitting a segment moves the chapter marks, and the longest title is not
    the modal one. And it requires the candidates to draw on the same pool of
    stream segments as the longest title -- decoys are permutations of one
    pool, whereas the episodes on a TV disc are similar in length but use
    disjoint segments. Without that check, a season disc looks exactly like an
    obfuscated movie.

    Counted against real discs: RED 2 scores 130. Kick-Ass (2009) scores 3
    (feature, BonusView, documentary). The Equalizer scores 1 -- its 2:35
    Vengeance Mode is far enough from the 2:12 feature to fall outside the
    window. Only the first should trip the threshold.
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


def is_obfuscated(titles):
    return len(decoy_cluster(titles)) > config.DECOY_CLUSTER_THRESHOLD


def segment_order_consistency(titles):
    """How strongly the cluster agrees on one relative segment order, 0..1.

    This separates combinatorial obfuscation from a disc that merely has
    several long titles. Under obfuscation the variants are subsequences of one
    canonical order, so ordering tests find almost nothing and the real
    difference is which short segments each one includes.

    Measured rather than asserted, because "almost" is doing work: on RED 2,
    129 of the 130 variants agree and exactly one -- 00123.mpls(2), the
    shortest -- is genuinely scrambled. A strict unanimity test would call that
    disc inconsistent and miss the pattern entirely.
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


def segment_order_is_consistent(titles, threshold=0.98):
    return segment_order_consistency(titles) >= threshold


def select_feature(titles, expected_seconds=None):
    """Pick the feature, or None if the disc needs help.

    With a known runtime, match against it -- that beats "longest title",
    which picks The Equalizer's 2:35 Vengeance Mode over the 2:12 film.
    Without one, fall back to longest, but only when nothing else is close.
    """
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
    """The triage block written into the manifest before ripping."""
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
