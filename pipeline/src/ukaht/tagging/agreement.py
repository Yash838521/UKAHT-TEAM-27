"""Measurement of agreement between annotators on the shared block.

A reference set produced by a single annotator carries no evidence that its
labels are reliable, because there is nothing against which the consistency of
those labels can be judged. Where two annotators label the same images
independently, the extent of their agreement measures whether the term
definitions are clear enough to be applied consistently.

Two statistics are reported according to the cardinality of each facet. For
facets taking one value, Cohen's kappa gives agreement corrected for the level
expected by chance, which raw agreement overstates whenever one value
predominates. For facets taking several values, Jaccard similarity gives the
proportion of terms both annotators selected out of those either selected.

Disagreements are listed per facet so that the term definitions responsible can
be revised before the reference set is used for measurement.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ukaht.tagging import vocabulary as vocab

EXCLUSIVE_FACETS = ("scene_type", "people", "shot_type", "room")
MULTI_LABEL_FACETS = ("structure", "orientation", "activity", "nature", "condition")

CONDITIONAL_ON_SCENE = {"room": "interior", "structure": "exterior"}
CONDITIONAL_ON_PEOPLE = ("orientation", "activity")

INTERPRETATION = (
    (0.81, "almost perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.01, "slight"),
    (-1.0, "none beyond chance"),
)


@dataclass(frozen=True)
class FacetAgreement:
    """Agreement between two annotators on one facet."""

    facet: str
    kind: str
    compared: int
    agreed: int
    statistic: float
    observed: float
    expected: float | None

    @property
    def reading(self) -> str:
        for threshold, label in INTERPRETATION:
            if self.statistic >= threshold:
                return label
        return "none beyond chance"


def _values(cell: object) -> set[str]:
    return {part.strip() for part in str(cell or "").split("|") if part.strip()}


def _applicable(first: dict, second: dict, facet_key: str) -> bool:
    """Return whether a facet applies according to both annotators."""
    if facet_key in CONDITIONAL_ON_SCENE:
        scene = CONDITIONAL_ON_SCENE[facet_key]
        return (
            str(first.get("scene_type", "")).strip() == scene
            and str(second.get("scene_type", "")).strip() == scene
        )
    if facet_key in CONDITIONAL_ON_PEOPLE:
        return (
            str(first.get("people", "")).strip() not in ("", "no_people")
            and str(second.get("people", "")).strip() not in ("", "no_people")
        )
    return True


def cohens_kappa(pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    """Return kappa with the observed and chance-expected agreement."""
    if not pairs:
        return 0.0, 0.0, 0.0

    total = len(pairs)
    observed = sum(1 for first, second in pairs if first == second) / total

    first_counts = Counter(first for first, _ in pairs)
    second_counts = Counter(second for _, second in pairs)
    categories = set(first_counts) | set(second_counts)

    expected = sum(
        (first_counts[category] / total) * (second_counts[category] / total)
        for category in categories
    )

    if expected >= 1.0:
        return 1.0, observed, expected

    return (observed - expected) / (1 - expected), observed, expected


def jaccard(pairs: list[tuple[set[str], set[str]]]) -> tuple[float, float]:
    """Return mean Jaccard similarity and the proportion of exact matches."""
    if not pairs:
        return 0.0, 0.0

    scores = []
    exact = 0
    for first, second in pairs:
        union = first | second
        if not union:
            scores.append(1.0)
            exact += 1
            continue
        scores.append(len(first & second) / len(union))
        if first == second:
            exact += 1

    return sum(scores) / len(scores), exact / len(pairs)


def load_sheet(path: Path) -> dict[str, dict]:
    """Load an annotation sheet keyed by image identifier."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if any(row.values())]

    return {
        str(row["image_uid"]).strip(): row
        for row in rows
        if str(row.get("image_uid", "")).strip()
        and str(row.get("scene_type", "")).strip()
    }


def compare_facet(
    shared: list[tuple[dict, dict]], facet_key: str
) -> FacetAgreement | None:
    """Return agreement on one facet across the shared images."""
    applicable = [
        (first, second)
        for first, second in shared
        if _applicable(first, second, facet_key)
    ]
    if len(applicable) < 2:
        return None

    if facet_key in EXCLUSIVE_FACETS:
        pairs = [
            (str(first.get(facet_key, "")).strip(), str(second.get(facet_key, "")).strip())
            for first, second in applicable
        ]
        pairs = [(a, b) for a, b in pairs if a and b]
        if len(pairs) < 2:
            return None
        statistic, observed, expected = cohens_kappa(pairs)
        agreed = sum(1 for a, b in pairs if a == b)
        return FacetAgreement(
            facet=facet_key,
            kind="kappa",
            compared=len(pairs),
            agreed=agreed,
            statistic=statistic,
            observed=observed,
            expected=expected,
        )

    pairs = [
        (_values(first.get(facet_key)), _values(second.get(facet_key)))
        for first, second in applicable
    ]
    statistic, exact = jaccard(pairs)
    return FacetAgreement(
        facet=facet_key,
        kind="jaccard",
        compared=len(pairs),
        agreed=int(exact * len(pairs)),
        statistic=statistic,
        observed=exact,
        expected=None,
    )


def disagreements(
    shared: list[tuple[dict, dict]], facet_key: str, names: tuple[str, str]
) -> list[dict]:
    """Return the images on which the two annotators differed."""
    records = []

    for first, second in shared:
        if not _applicable(first, second, facet_key):
            continue

        if facet_key in EXCLUSIVE_FACETS:
            a = str(first.get(facet_key, "")).strip()
            b = str(second.get(facet_key, "")).strip()
            if a and b and a != b:
                records.append(
                    {
                        "facet": facet_key,
                        "image_uid": first["image_uid"],
                        "file_name": first.get("file_name", ""),
                        names[0]: a,
                        names[1]: b,
                    }
                )
        else:
            a = _values(first.get(facet_key))
            b = _values(second.get(facet_key))
            if a != b:
                records.append(
                    {
                        "facet": facet_key,
                        "image_uid": first["image_uid"],
                        "file_name": first.get("file_name", ""),
                        names[0]: "|".join(sorted(a)),
                        names[1]: "|".join(sorted(b)),
                    }
                )

    return records


def confusion(shared: list[tuple[dict, dict]], facet_key: str) -> pd.DataFrame:
    """Return a table of how often each pair of terms was chosen together."""
    counts: dict[tuple[str, str], int] = defaultdict(int)

    for first, second in shared:
        if not _applicable(first, second, facet_key):
            continue
        a = str(first.get(facet_key, "")).strip()
        b = str(second.get(facet_key, "")).strip()
        if a and b:
            counts[(a, b)] += 1

    if not counts:
        return pd.DataFrame()

    terms = sorted({term for pair in counts for term in pair})
    table = pd.DataFrame(0, index=terms, columns=terms)
    for (a, b), count in counts.items():
        table.loc[a, b] = count
    return table


def format_report(
    results: list[FacetAgreement], shared_count: int, names: tuple[str, str]
) -> str:
    """Return a readable account of agreement between the two annotators."""
    lines = [
        f"Annotators: {names[0]} and {names[1]}",
        f"Images labelled by both: {shared_count}",
        "",
        f"{'facet':<14}{'measure':<10}{'compared':>10}{'agreed':>8}{'statistic':>11}  interpretation",
        "-" * 72,
    ]

    for result in results:
        lines.append(
            f"{result.facet:<14}{result.kind:<10}{result.compared:>10}"
            f"{result.agreed:>8}{result.statistic:>11.3f}  {result.reading}"
        )

    kappas = [item for item in results if item.kind == "kappa"]
    jaccards = [item for item in results if item.kind == "jaccard"]

    lines.append("-" * 72)
    if kappas:
        mean = sum(item.statistic for item in kappas) / len(kappas)
        lines.append(f"{'mean kappa':<14}{'':<10}{'':>10}{'':>8}{mean:>11.3f}")
    if jaccards:
        mean = sum(item.statistic for item in jaccards) / len(jaccards)
        lines.append(f"{'mean jaccard':<14}{'':<10}{'':>10}{'':>8}{mean:>11.3f}")

    lines.append("")
    lines.append(
        "Kappa corrects for the agreement expected by chance and is reported for facets"
    )
    lines.append(
        "taking a single value. Jaccard similarity is reported where several terms may"
    )
    lines.append("apply, and is not chance-corrected.")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure agreement between two annotators on the shared block"
    )
    parser.add_argument("--first", type=Path, required=True, help="first sheet")
    parser.add_argument("--second", type=Path, required=True, help="second sheet")
    parser.add_argument("--names", nargs=2, default=["first", "second"])
    parser.add_argument("--output", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args(argv)

    problems = vocab.validate()
    if problems:
        raise ValueError("vocabulary validation failed: " + "; ".join(problems))

    first_sheet = load_sheet(args.first)
    second_sheet = load_sheet(args.second)
    names = (args.names[0], args.names[1])

    common = sorted(set(first_sheet) & set(second_sheet))
    if len(common) < 5:
        print(f"Only {len(common)} images were labelled by both; too few to compare")
        return 1

    shared = [(first_sheet[uid], second_sheet[uid]) for uid in common]

    results = []
    for facet_key in EXCLUSIVE_FACETS + MULTI_LABEL_FACETS:
        result = compare_facet(shared, facet_key)
        if result is not None:
            results.append(result)

    if not results:
        print("No facet had enough shared annotation to compare")
        return 1

    print(format_report(results, len(shared), names))

    all_disagreements = []
    for facet_key in EXCLUSIVE_FACETS + MULTI_LABEL_FACETS:
        all_disagreements.extend(disagreements(shared, facet_key, names))

    if all_disagreements:
        counts = Counter(row["facet"] for row in all_disagreements)
        print()
        print(f"Disagreements: {len(all_disagreements)}")
        for facet_key, count in counts.most_common():
            print(f"  {facet_key:<14} {count:>3}")

    args.output.mkdir(parents=True, exist_ok=True)

    summary = pd.DataFrame(
        {
            "facet": item.facet,
            "measure": item.kind,
            "compared": item.compared,
            "agreed": item.agreed,
            "statistic": round(item.statistic, 4),
            "observed_agreement": round(item.observed, 4),
            "expected_agreement": None if item.expected is None else round(item.expected, 4),
            "interpretation": item.reading,
            "vocabulary_version": vocab.VERSION,
        }
        for item in results
    )
    summary.to_csv(args.output / "annotator_agreement.csv", index=False)

    if all_disagreements:
        pd.DataFrame(all_disagreements).to_csv(
            args.output / "annotator_disagreements.csv", index=False
        )

    for facet_key in EXCLUSIVE_FACETS:
        table = confusion(shared, facet_key)
        if not table.empty:
            table.to_csv(args.output / f"confusion_{facet_key}.csv")

    print()
    print(f"Summary: {args.output / 'annotator_agreement.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())