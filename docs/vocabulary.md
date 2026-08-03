# Controlled Vocabulary

**Version:** 1.0
**Status:** revised following validation against unseen images
**Maintainer:** Saisha
**Derived from:** client search requirements and a stratified sample of 39 images
drawn from all ten archive directories, then revised following a validation pass
against 27 further images not used during development

This document lists every term the system uses to describe images, with a rule
for when each applies and the prompt text used for automatic matching.

---

## 1. Structure

Terms are organised into eight facets. An image receives values from several
facets at once rather than a single label.

| Facet | Cardinality | Source |
|---|---|---|
| Site | One per image | Directory path |
| Scene type | One per image | Image content |
| Room | Zero or one, interior only | Image content |
| Structure | Zero or more, exterior only | Image content and site maps |
| People | One per image | Image content |
| Activity | Zero or more | Image content |
| Nature and wildlife | Zero or more | Image content |
| Condition | Zero or more | Image content |
| Object tags | Zero or more | Image content |

Facets are separated because a single label cannot answer the client's search
cases. An image can be an exterior view of Base A showing a generator shed with
two people working and visible paint loss. Flat labelling loses most of that.

---

## 2. Site

Sites are read from the archive directory structure rather than from image
content, giving complete coverage. Names follow client usage.

| Term | Directory marker | Images in supplied dataset |
|---|---|---|
| Base A, Port Lockroy | `_A_` | 762 |
| Base W, Detaille Island | `_W_` | 143 |
| Base E, Stonington Island | `_E_` | 103 |
| Base F, Wordie House | `_F_` | 0 |
| Base Y, Horseshoe Island | `_Y_` | 0 |
| Blaiklock Island Refuge | not yet observed | 0 |
| Damoy Hut | not yet observed | 0 |
| Endurance Shipwreck | not yet observed | 0 |

Five sites are held in the vocabulary but are not represented in the supplied
dataset. Directory markers for Blaiklock, Damoy and Endurance require
confirmation before images from those sites can be ingested.

---

## 3. Scene type

Exactly one value per image.

| Term | Applies when | Does not apply when | Prompt |
|---|---|---|---|
| Exterior | A built structure is the subject of the photograph and the view is outdoors | The image is outdoors but contains no building, or a building is incidental to a wide landscape | a photograph taken outdoors showing the outside of a building |
| Interior | The view is from inside a building and room context is visible | The subject is an isolated object with no room visible | a photograph taken inside a room of a building |
| Landscape | Outdoors with terrain, sea, sky, ice, wildlife or loose objects as the subject and no building as the subject | A structure is the subject of the frame | a wide outdoor photograph of a snowy landscape with no buildings |
| Object study | A single object or small group is photographed against a plain or neutral background for record purposes | The surrounding room or site is legible | a photograph of a single object against a plain background |

Object study exists because three images in the sample could not be placed as
either interior or exterior. Their surroundings are deliberately excluded by the
photographer, which is itself informative: these are catalogue records.

---

## 4. Room

Zero or one value, applied only to interior images. Room is inferred from
visible contents, not from assumed building layout.

| Term | Evidence that supports it | Prompt |
|---|---|---|
| Living room | Seating, stove or heater, table, radio, personal items | the inside of a living room with chairs and a heating stove |
| Kitchen | Cooking range, food tins, packets, plates, cups, kitchenware | the inside of a kitchen with food tins and cooking equipment |
| Workshop | Hand tools, workbench, paint tins, fixings, machinery | the inside of a workshop with tools and work equipment |
| Bunkroom | Bunks or beds, blankets, personal clothing, storage crates | a bedroom with bunk beds and blankets |
| Radio room | Radio sets, headphones, switch panels, wiring, papers | a room containing radio equipment and electrical switches |
| Storage | Stacked shelving of supplies and containers without cooking or work equipment | shelves stacked with supplies and containers |
| Museum display | Objects arranged for public viewing with interpretation panels | a museum display of historic objects with information panels |
| Room not determined | Interior with insufficient visible context | — |

Museum display is separated from the working-room terms because such images
show present-day interpretation rather than historic use. Both occur in the
sample.

---

## 5. Structure

Zero or more values, exterior images only.

| Term | Prompt |
|---|---|
| Main hut | a large wooden hut in a snowy landscape |
| Generator shed | a small outbuilding housing a generator |
| Emergency shed | a small emergency shelter building |
| Anemometer tower | a tall metal tower carrying wind measuring instruments |
| Radio tower | a tall radio mast or antenna |
| Outbuilding | a small outbuilding beside a larger hut |
| Structure not identified | — |

Distinguishing a generator shed from an emergency shed is not reliably possible
from image content alone, since both are small outbuildings of similar
construction. Accurate assignment depends on site maps identifying which
building stands where. Until those are available, such images receive
"Outbuilding" and are flagged for review.

---

## 6. People

Exactly one value per image.

| Term | Applies when | Prompt |
|---|---|---|
| No people | No person or body part is visible | — |
| Person alone | One person is visible | a photograph of one person |
| Two people | Exactly two people are visible | a photograph of two people together |
| Group | Three or more people are visible | a photograph of a group of people |
| Part of a person | Only a hand, arm or partial figure appears, usually holding an object | a hand holding an object |

Part of a person exists because the sample contains an image where only a hand
is visible. Counting it as a person overstates people coverage; counting it as
no people loses the fact that someone is present.

### Orientation

Zero or more, applied where a person is visible.

| Term | Applies when | Prompt |
|---|---|---|
| Facing the camera | The person's face is turned towards the lens | a person looking towards the camera |
| Back to the camera | The person is seen from behind | a person photographed from behind |
| Side on | The person is in profile, facing neither towards nor away | a person seen from the side in profile |
| Mixed orientation | Several people face in different directions | a group of people facing in different directions |

Side on and mixed orientation were added during validation. Two images showed a
person in profile, and one showed a group facing several ways; none of these
could be recorded with the original pair of terms.

---

## 7. Activity

Zero or more, applied where a person is visible.

| Term | Prompt |
|---|---|
| Working | a person working with tools or equipment |
| Walking | a person walking outdoors in the snow |
| Cooking | a person cooking food |
| Sleeping | a person sleeping in a bunk |
| Skiing | a person skiing across snow |
| Playing music | a person playing a musical instrument |
| Reading or writing | a person reading or writing at a desk |
| Standing or posing | a person standing still facing the camera |
| Resting | people sitting or lying at ease |

Reading or writing was added from the development sample and resting from the
validation pass, where a group photograph showed people at ease rather than
posing. The remaining terms follow the client's stated search cases.

---

## 8. Nature and wildlife

Zero or more.

| Term | Prompt |
|---|---|
| Penguin | penguins standing on snow or rock |
| Dog | sled dogs in the snow |
| Seal | a seal resting on ice |
| Bird | a flying bird over the sea |
| Whale | a whale at the surface of the sea |
| Snow | ground covered in snow |
| Sea ice | frozen sea ice |
| Iceberg | a detached iceberg floating in open water |
| Glacier or ice cliff | a glacier front or ice cliff meeting the sea |
| Exposed rock | bare rock without snow cover |
| Mountains | snow-covered mountains in the distance |
| Open water | open sea water |
| Coastline | a coastline where land meets the sea |
| Sunset | a sunset sky over the sea or mountains |
| Overcast or storm | heavy grey cloud or blowing snow |
| Clear sky | a clear blue sky |

Exposed rock is kept separate from snow. Several sample images show rock as the
dominant terrain, and collapsing this into a general snow term would lose it.

Glacier or ice cliff was added during validation. One image showed a large ice
mass across water that could be either a floating iceberg or an ice cliff at the
shore; the distinction is not always determinable from a photograph, so both
terms exist and either may be applied where the form is unclear.

---

## 9. Condition

Zero or more. Serves conservation recording rather than the promotional search
cases.

| Term | Applies when | Prompt |
|---|---|---|
| Weathered timber | Wood is greyed, split or eroded by exposure | weathered and greyed timber boarding |
| Paint loss | Paint is flaking, peeling or worn away | flaking and peeling paint on a painted surface |
| Rust or corrosion | Metal shows orange or brown oxidation | rusted and corroded metal |
| Structural damage | Breakage, collapse or displacement of building fabric | broken or collapsed building structure |
| Object wear | An artefact shows handling wear, cracking or discolouration | a worn and aged historic object |
| No visible deterioration | Surfaces appear sound | — |

---

## 10. Shot type

Exactly one value per image.

| Term | Applies when | Prompt |
|---|---|---|
| Wide view | The whole structure, room or landscape is in frame | a wide photograph showing a whole building or landscape |
| Medium view | A substantial part of a subject, such as one wall or one shelf unit | a photograph of part of a building or a section of shelving |
| Detail | A single feature or object fills the frame | a close-up photograph of a small detail |

Shot type matters for conservation work: a detail of a corroded joint serves a
different purpose from a general view of the same building.

---

## 11. Object tags

Zero or more. Grouped for readability; the groups are not separate facets.

### Building fabric and exterior fittings

roof · wall · window · door · doorway · timber cladding · metal cladding ·
beam · truss · cement · cement pillar · steps · walkway · post · ladder ·
cable · gas cylinder · fuel drum · crate · detritus · rope

### Living and domestic

stove · fire · heater · shelf · seat · chair · table · cupboard · cabinet ·
bed · bunk · blanket · curtain · carpet · furniture

### Kitchen and provisions

food tin · food packet · jar · bottle · flask · plate · cup · enamel bowl ·
tray · packaging

### Workshop and equipment

hand tool · hammer · saw · nail · paint tin · workbench · machinery ·
mechanical component · gauge · dial · compass · instrument · instrument case ·
ruler

### Radio and electrical

radio set · headphones · wiring · switch panel · electrical component ·
antenna

### Clothing and personal

boots · footwear · jacket · clothing · glove · hat · flag · whale bone

### Paper and archive material

photograph · postcard · stamp · envelope · printed card · book · paper record ·
document · information panel · label · plaque

### Transport and vessels

ship · boat · sledge

### Containers

box · case · canister

### Photographic reference objects

colour reference chart · scale card

The last group records items placed in frame by the photographer rather than
belonging to the site. They are strong indicators that an image is a catalogue
record and are useful for filtering record shots in or out.

---

## 12. Terms deliberately excluded

| Excluded | Reason |
|---|---|
| Heritage | Applies to every image in the archive; cannot narrow a result set |
| Conservation | Describes purpose rather than content; replaced by the condition facet |
| Documentation | Describes purpose rather than content; replaced by shot type |
| Historic | Applies to substantially all content |
| Museum | Ambiguous between a display setting and an institution; replaced by Museum display under Room |
| Antarctic | Applies to the whole archive |
| Artefact | Too broad to narrow a search; replaced by specific object tags |

These terms appeared frequently during coding, but a term matching almost every
image cannot support retrieval. They remain useful as prose in captions.

---

## 13. Validation

The vocabulary was tested against 27 images drawn from the archive using a
different random seed and excluding every image used during development. Terms
were assigned using only the published list; where no term fitted, the gap was
recorded rather than approximated.

### Coverage

| Facet | Assigned | Applicable | Coverage |
|---|---|---|---|
| Scene type | 27 | 27 | 100% |
| People | 27 | 27 | 100% |
| Shot type | 27 | 27 | 100% |
| Room | 5 | 5 interiors | 100% |
| Structure | 6 | 7 exteriors | 86% |
| Condition | 22 | 27 | 81% |
| Nature and wildlife | 13 | 27 | 48% |
| Activity | 3 | 27 | 11% |
| Orientation | 1 | 27 | 4% |

The three required facets reached complete coverage. Room reached complete
coverage on the images to which it applies. The remaining facets are optional by
design and their figures reflect image content rather than gaps in the terms:
only three images contained a person, which bounds activity and orientation.

Object tags: 41 of the 83 available terms were applied across 27 images. Terms
per image ranged from 4 to 17, with a mean of 9.4.

### Scene distribution

| Scene type | Images |
|---|---|
| Object study | 9 |
| Exterior | 7 |
| Landscape | 6 |
| Interior | 5 |

Object study, added during development because three images could not be placed
as interior or exterior, proved to be the largest single category in the
validation sample. This supports its inclusion.

### Changes arising

| Change | Evidence |
|---|---|
| Added `side_on` to orientation | Two images showed a person in profile, fitting neither existing term |
| Added `mixed_orientation` | One group photograph showed people facing several directions |
| Added `resting` to activity | A group image showed people at ease, not posing |
| Added `glacier` to nature | An ice mass could not be resolved as iceberg or ice cliff |
| Added object tags `rope`, `cabinet`, `flask`, `ruler`, `instrument case` | Recorded as needed but unavailable during annotation |
| Added a containers group: `box`, `case`, `canister` | Labelled cases and boxes appeared with no suitable term |
| Aligned `flag`, `whale bone` and `blanket` between document and code | Present in one but not the other |

### Terms not exercised

The following did not occur in the validation sample: five room terms, four
structure terms, two people terms, five activity terms and five nature terms.

For room and activity this reflects sample composition rather than a fault in
the terms, since only five interiors and three images with people were drawn.
The structure terms are treated separately below.

### Structure identification

Four of the six exterior images were recorded as `outbuilding` because the
identity of the building could not be established from the photograph. The terms
`generator_shed`, `emergency_shed`, `anemometer_tower` and `radio_tower` were
not applied to any image.

This confirms as a measured result what was previously an expectation: small
outbuildings at these sites are of similar construction and cannot be
distinguished from image content alone. Reliable assignment requires site maps
identifying which building stands where. Until those are available, exterior
images receive `outbuilding` and the more specific terms remain unused.

The single uncovered exterior was an outdoor image containing a sledge and
wildlife but no building. Under the definition in section 3 this is a landscape,
and the scene type boundary has been clarified accordingly: exterior requires a
built structure as the subject of the photograph.

### Ambiguity

Sixteen of the 27 images carried a note recording a difficult choice. Most
record a refusal to infer beyond what the image shows: building identity not
visible, garment type unclear, ice formation indeterminate. Two record genuine
overlap between terms, both concerning the boundary between `radio_room` and
`museum_display`, where a room containing radio equipment is also arranged for
public interpretation. Where both apply, `museum_display` takes precedence, since
it describes the room's present function.

Two images in the sample were near-identical views of the same object,
independently confirming that near-duplicate detection is required before
results are presented to users.

## 14. Open items for the client

1. Site maps identifying named structures at each site, referenced in the search
   requirements and needed to distinguish generator shed, emergency shed and
   towers.
2. Directory markers used for Blaiklock Island Refuge, Damoy Hut and Endurance
   Shipwreck, so that images from those sites can be recognised on ingest.
3. Confirmation that no images from Wordie House, Horseshoe Island, Blaiklock,
   Damoy or Endurance are present in the supplied dataset.
4. Whether people-focused material forms a distinct part of the wider archive,
   given how little appears in the supplied images.
5. Review and approval of the terms in sections 3 to 11.

---

## 15. Revision record

| Version | Date | Change |
|---|---|---|
| 0.9 | | Initial draft from coding sample and client search requirements |
| 1.0 | | Revised after validation against 27 unseen images: nine terms added, scene type boundary clarified, structure limitation evidenced |