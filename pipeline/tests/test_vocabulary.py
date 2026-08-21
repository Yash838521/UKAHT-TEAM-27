"""Tests for the controlled vocabulary."""

from __future__ import annotations

import pytest

from ukaht.tagging import vocabulary as vocab


def test_vocabulary_is_internally_consistent() -> None:
    assert vocab.validate() == []


def test_every_facet_has_terms() -> None:
    for facet in vocab.FACETS:
        assert facet.terms, f"{facet.key} has no terms"


def test_term_keys_are_unique_within_a_facet() -> None:
    for facet in vocab.FACETS:
        keys = facet.keys
        assert len(keys) == len(set(keys)), f"{facet.key} has duplicate keys"


def test_excluded_terms_do_not_appear() -> None:
    live = {term.key for facet in vocab.FACETS for term in facet.terms}
    live |= {tag.replace(" ", "_") for tag in vocab.object_tags()}
    for excluded in vocab.EXCLUDED_TERMS:
        assert excluded not in live


@pytest.mark.parametrize(
    "facet_key",
    ["scene_type", "people", "shot_type", "site", "room"],
)
def test_exclusive_facets_are_marked_exclusive(facet_key: str) -> None:
    assert vocab.facet(facet_key).exclusive


@pytest.mark.parametrize(
    "facet_key",
    ["structure", "activity", "nature", "condition", "orientation"],
)
def test_repeatable_facets_are_not_exclusive(facet_key: str) -> None:
    assert not vocab.facet(facet_key).exclusive


def test_room_applies_only_to_interiors() -> None:
    assert vocab.facet("room").applies_to == ("interior",)


def test_structure_applies_only_to_exteriors() -> None:
    assert vocab.facet("structure").applies_to == ("exterior",)


@pytest.mark.parametrize(
    "site_key",
    [
        "base_a",
        "base_w",
        "base_e",
        "base_f",
        "base_y",
        "blaiklock",
        "damoy",
        "endurance",
    ],
)
def test_all_named_sites_are_present(site_key: str) -> None:
    assert vocab.facet("site").get(site_key) is not None


@pytest.mark.parametrize(
    ("facet_key", "term_key"),
    [
        ("room", "living_room"),
        ("room", "kitchen"),
        ("room", "workshop"),
        ("room", "bunkroom"),
        ("room", "radio_room"),
        ("structure", "main_hut"),
        ("structure", "generator_shed"),
        ("structure", "emergency_shed"),
        ("structure", "anemometer_tower"),
        ("structure", "radio_tower"),
        ("people", "person_alone"),
        ("people", "group"),
        ("orientation", "facing_camera"),
        ("orientation", "back_to_camera"),
        ("activity", "walking"),
        ("activity", "working"),
        ("activity", "cooking"),
        ("activity", "sleeping"),
        ("activity", "skiing"),
        ("activity", "music"),
        ("nature", "penguin"),
        ("nature", "dog"),
        ("nature", "iceberg"),
        ("nature", "sunset"),
        ("nature", "snow"),
        ("nature", "exposed_rock"),
    ],
)
def test_requested_terms_are_covered(facet_key: str, term_key: str) -> None:
    assert vocab.facet(facet_key).get(term_key) is not None


@pytest.mark.parametrize(
    "tag",
    [
        "gas cylinder",
        "ladder",
        "cable",
        "detritus",
        "cement pillar",
        "roof",
        "wall",
        "window",
        "door",
        "crate",
        "truss",
        "beam",
        "stove",
        "food tin",
        "food packet",
        "plate",
        "cup",
        "bottle",
        "paint tin",
        "hammer",
        "saw",
        "nail",
        "blanket",
        "jacket",
        "clothing",
        "bunk",
        "headphones",
        "wiring",
        "switch panel",
        "shelf",
        "seat",
        "cupboard",
        "table",
        "photograph",
    ],
)
def test_requested_object_tags_are_covered(tag: str) -> None:
    assert tag in vocab.object_tags()


def test_object_tags_have_no_duplicates() -> None:
    tags = vocab.object_tags()
    assert len(tags) == len(set(tags))


def test_prompts_exist_for_content_derived_facets() -> None:
    for facet_key in ("scene_type", "room", "structure", "nature", "condition"):
        prompts = vocab.prompts_for(facet_key)
        assert prompts, f"{facet_key} has no prompts"


def test_prompts_are_descriptive_phrases() -> None:
    for facet_prompts in vocab.all_prompts().values():
        for key, prompt in facet_prompts.items():
            assert prompt == prompt.lower(), f"{key} prompt should be lower case"
            assert len(prompt.split()) >= 3, f"{key} prompt is too short"


def test_site_terms_are_not_content_derived() -> None:
    assert vocab.prompts_for("site") == {}