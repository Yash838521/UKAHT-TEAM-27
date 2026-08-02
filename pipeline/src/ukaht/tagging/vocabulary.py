"""Controlled vocabulary for archive image description.

Terms are grouped into facets. Each facet declares whether it is exclusive, the
scene types it applies to, and the terms it contains. Terms carry the prompt
text used for automatic matching, or None where a term is assigned by rule
rather than by image content.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VERSION = "0.9"

@dataclass(frozen=True)
class Term:
    """A single vocabulary term."""

    key: str
    label: str
    prompt: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Facet:
    """A group of terms describing one dimension of an image."""

    key: str
    label: str
    exclusive: bool
    terms: tuple[Term, ...]
    applies_to: tuple[str, ...] = ()
    optional: bool = True

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(term.key for term in self.terms)

    def get(self, key: str) -> Term | None:
        for term in self.terms:
            if term.key == key:
                return term
        return None

    def prompts(self) -> dict[str, str]:
        return {term.key: term.prompt for term in self.terms if term.prompt}


SITE = Facet(
    key="site",
    label="Site",
    exclusive=True,
    optional=False,
    terms=(
        Term("base_a", "Base A, Port Lockroy", None, "directory marker _A_"),
        Term("base_w", "Base W, Detaille Island", None, "directory marker _W_"),
        Term("base_e", "Base E, Stonington Island", None, "directory marker _E_"),
        Term("base_f", "Base F, Wordie House", None, "directory marker _F_"),
        Term("base_y", "Base Y, Horseshoe Island", None, "directory marker _Y_"),
        Term("blaiklock", "Blaiklock Island Refuge", None, "marker to be confirmed"),
        Term("damoy", "Damoy Hut", None, "marker to be confirmed"),
        Term("endurance", "Endurance Shipwreck", None, "marker to be confirmed"),
        Term("site_unknown", "Site not determined"),
    ),
)

SCENE_TYPE = Facet(
    key="scene_type",
    label="Scene type",
    exclusive=True,
    optional=False,
    terms=(
        Term(
            "exterior",
            "Exterior",
            "a photograph taken outdoors showing the outside of a building",
        ),
        Term("interior", "Interior", "a photograph taken inside a room of a building"),
        Term(
            "landscape",
            "Landscape",
            "a wide outdoor photograph of a snowy landscape with no buildings",
        ),
        Term(
            "object_study",
            "Object study",
            "a photograph of a single object against a plain background",
        ),
    ),
)

ROOM = Facet(
    key="room",
    label="Room",
    exclusive=True,
    applies_to=("interior",),
    terms=(
        Term(
            "living_room",
            "Living room",
            "the inside of a living room with chairs and a heating stove",
        ),
        Term(
            "kitchen",
            "Kitchen",
            "the inside of a kitchen with food tins and cooking equipment",
        ),
        Term(
            "workshop",
            "Workshop",
            "the inside of a workshop with tools and work equipment",
        ),
        Term("bunkroom", "Bunkroom", "a bedroom with bunk beds and blankets"),
        Term(
            "radio_room",
            "Radio room",
            "a room containing radio equipment and electrical switches",
        ),
        Term("storage", "Storage", "shelves stacked with supplies and containers"),
        Term(
            "museum_display",
            "Museum display",
            "a museum display of historic objects with information panels",
        ),
        Term("room_unknown", "Room not determined"),
    ),
)

STRUCTURE = Facet(
    key="structure",
    label="Structure",
    exclusive=False,
    applies_to=("exterior",),
    terms=(
        Term("main_hut", "Main hut", "a large wooden hut in a snowy landscape"),
        Term(
            "generator_shed",
            "Generator shed",
            "a small outbuilding housing a generator",
            "reliable assignment requires site maps",
        ),
        Term(
            "emergency_shed",
            "Emergency shed",
            "a small emergency shelter building",
            "reliable assignment requires site maps",
        ),
        Term(
            "anemometer_tower",
            "Anemometer tower",
            "a tall metal tower carrying wind measuring instruments",
        ),
        Term("radio_tower", "Radio tower", "a tall radio mast or antenna"),
        Term("outbuilding", "Outbuilding", "a small outbuilding beside a larger hut"),
        Term("structure_unknown", "Structure not identified"),
    ),
)

PEOPLE = Facet(
    key="people",
    label="People",
    exclusive=True,
    optional=False,
    terms=(
        Term("no_people", "No people"),
        Term("person_alone", "Person alone", "a photograph of one person"),
        Term("two_people", "Two people", "a photograph of two people together"),
        Term("group", "Group", "a photograph of a group of people"),
        Term("partial_person", "Part of a person", "a hand holding an object"),
    ),
)

ORIENTATION = Facet(
    key="orientation",
    label="Orientation",
    exclusive=False,
    terms=(
        Term("facing_camera", "Facing the camera", "a person looking towards the camera"),
        Term(
            "back_to_camera",
            "Back to the camera",
            "a person photographed from behind",
        ),
    ),
)

ACTIVITY = Facet(
    key="activity",
    label="Activity",
    exclusive=False,
    terms=(
        Term("working", "Working", "a person working with tools or equipment"),
        Term("walking", "Walking", "a person walking outdoors in the snow"),
        Term("cooking", "Cooking", "a person cooking food"),
        Term("sleeping", "Sleeping", "a person sleeping in a bunk"),
        Term("skiing", "Skiing", "a person skiing across snow"),
        Term("music", "Playing music", "a person playing a musical instrument"),
        Term(
            "reading_writing",
            "Reading or writing",
            "a person reading or writing at a desk",
        ),
        Term("posing", "Standing or posing", "a person standing still facing the camera"),
    ),
)

NATURE = Facet(
    key="nature",
    label="Nature and wildlife",
    exclusive=False,
    terms=(
        Term("penguin", "Penguin", "penguins standing on snow or rock"),
        Term("dog", "Dog", "sled dogs in the snow"),
        Term("seal", "Seal", "a seal resting on ice"),
        Term("bird", "Bird", "a flying bird over the sea"),
        Term("whale", "Whale", "a whale at the surface of the sea"),
        Term("snow", "Snow", "ground covered in snow"),
        Term("sea_ice", "Sea ice", "frozen sea ice"),
        Term("iceberg", "Iceberg", "an iceberg floating in the sea"),
        Term("exposed_rock", "Exposed rock", "bare rock without snow cover"),
        Term("mountains", "Mountains", "snow-covered mountains in the distance"),
        Term("open_water", "Open water", "open sea water"),
        Term("coastline", "Coastline", "a coastline where land meets the sea"),
        Term("sunset", "Sunset", "a sunset sky over the sea or mountains"),
        Term("overcast", "Overcast or storm", "heavy grey cloud or blowing snow"),
        Term("clear_sky", "Clear sky", "a clear blue sky"),
    ),
)

CONDITION = Facet(
    key="condition",
    label="Condition",
    exclusive=False,
    terms=(
        Term(
            "weathered_timber",
            "Weathered timber",
            "weathered and greyed timber boarding",
        ),
        Term("paint_loss", "Paint loss", "flaking and peeling paint on a painted surface"),
        Term("rust", "Rust or corrosion", "rusted and corroded metal"),
        Term(
            "structural_damage",
            "Structural damage",
            "broken or collapsed building structure",
        ),
        Term("object_wear", "Object wear", "a worn and aged historic object"),
        Term("sound", "No visible deterioration"),
    ),
)

SHOT_TYPE = Facet(
    key="shot_type",
    label="Shot type",
    exclusive=True,
    optional=False,
    terms=(
        Term(
            "wide",
            "Wide view",
            "a wide photograph showing a whole building or landscape",
        ),
        Term(
            "medium",
            "Medium view",
            "a photograph of part of a building or a section of shelving",
        ),
        Term("detail", "Detail", "a close-up photograph of a small detail"),
    ),
)

OBJECT_GROUPS: dict[str, tuple[str, ...]] = {
    "building_fabric": (
        "roof",
        "wall",
        "window",
        "door",
        "doorway",
        "timber cladding",
        "metal cladding",
        "beam",
        "truss",
        "cement",
        "cement pillar",
        "steps",
        "walkway",
        "post",
        "ladder",
        "cable",
        "gas cylinder",
        "fuel drum",
        "crate",
        "detritus",
    ),
    "living_domestic": (
        "stove",
        "fire",
        "heater",
        "shelf",
        "seat",
        "chair",
        "table",
        "cupboard",
        "bed",
        "bunk",
        "blanket",
        "curtain",
        "carpet",
        "furniture",
    ),
    "kitchen_provisions": (
        "food tin",
        "food packet",
        "jar",
        "bottle",
        "plate",
        "cup",
        "enamel bowl",
        "tray",
        "packaging",
    ),
    "workshop_equipment": (
        "hand tool",
        "hammer",
        "saw",
        "nail",
        "paint tin",
        "workbench",
        "machinery",
        "mechanical component",
        "gauge",
        "dial",
        "compass",
        "instrument",
    ),
    "radio_electrical": (
        "radio set",
        "headphones",
        "wiring",
        "switch panel",
        "electrical component",
        "antenna",
    ),
    "clothing_personal": ("boots", "footwear", "jacket", "clothing", "glove", "hat"),
    "paper_archive": (
        "photograph",
        "postcard",
        "stamp",
        "envelope",
        "printed card",
        "book",
        "paper record",
        "document",
        "information panel",
        "label",
        "plaque",
    ),
    "transport": ("ship", "boat", "sledge"),
    "photographic_reference": ("colour reference chart", "scale card"),
}

EXCLUDED_TERMS: dict[str, str] = {
    "heritage": "applies to every image in the archive",
    "conservation": "describes purpose rather than content",
    "documentation": "describes purpose rather than content",
    "historic": "applies to substantially all content",
    "museum": "ambiguous; replaced by museum_display under room",
    "antarctic": "applies to the whole archive",
    "artefact": "too broad to narrow a search",
}

FACETS: tuple[Facet, ...] = (
    SITE,
    SCENE_TYPE,
    ROOM,
    STRUCTURE,
    PEOPLE,
    ORIENTATION,
    ACTIVITY,
    NATURE,
    CONDITION,
    SHOT_TYPE,
)

_BY_KEY = {facet.key: facet for facet in FACETS}


def facet(key: str) -> Facet:
    """Return a facet by key."""
    return _BY_KEY[key]


def object_tags() -> tuple[str, ...]:
    """Return every object tag across all groups."""
    return tuple(tag for group in OBJECT_GROUPS.values() for tag in group)


def prompts_for(facet_key: str) -> dict[str, str]:
    """Return prompt text for every term in a facet that has one."""
    return _BY_KEY[facet_key].prompts()


def all_prompts() -> dict[str, dict[str, str]]:
    """Return prompt text for every facet that supports automatic matching."""
    return {
        key: value.prompts() for key, value in _BY_KEY.items() if value.prompts()
    }


def validate() -> list[str]:
    """Return a list of consistency problems, empty when the vocabulary is sound."""
    problems: list[str] = []
    seen: dict[str, str] = {}

    for item in FACETS:
        if not item.terms:
            problems.append(f"{item.key} contains no terms")
        for term in item.terms:
            if term.key in seen and seen[term.key] != item.key:
                problems.append(
                    f"{term.key} appears in both {seen[term.key]} and {item.key}"
                )
            seen[term.key] = item.key
            if not term.label:
                problems.append(f"{item.key}.{term.key} has no label")

    tags = object_tags()
    duplicates = {tag for tag in tags if tags.count(tag) > 1}
    for tag in sorted(duplicates):
        problems.append(f"object tag {tag} is listed more than once")

    for excluded in EXCLUDED_TERMS:
        if excluded in seen:
            problems.append(f"{excluded} is excluded but present in {seen[excluded]}")

    return problems


def summary() -> str:
    """Return a readable summary of the vocabulary."""
    lines = [f"Vocabulary version {VERSION}", ""]
    total = 0

    for item in FACETS:
        kind = "one" if item.exclusive else "many"
        scope = f" [{', '.join(item.applies_to)}]" if item.applies_to else ""
        lines.append(f"  {item.label:<22} {len(item.terms):>3} terms  ({kind}){scope}")
        total += len(item.terms)

    lines.append("")
    for group, tags in OBJECT_GROUPS.items():
        lines.append(f"  {group:<22} {len(tags):>3} tags")
        total += len(tags)

    lines.append("")
    lines.append(f"  {'total':<22} {total:>3}")
    return "\n".join(lines)