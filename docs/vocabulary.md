# Controlled Vocabulary
**Version:** 0.9 (draft for client review)
**Derived from:** client search requirements and a stratified sample of 39 images
drawn from all ten archive directories

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
| Exterior | A built structure is the subject and the view is outdoors | The building is incidental to a wide landscape | a photograph taken outdoors showing the outside of a building |
| Interior | The view is from inside a building and room context is visible | The subject is an isolated object with no room visible | a photograph taken inside a room of a building |
| Landscape | Outdoors with terrain, sea, sky or ice as the subject and no building as the subject | A structure dominates the frame | a wide outdoor photograph of a snowy landscape with no buildings |
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

| Term | Prompt |
|---|---|
| Facing the camera | a person looking towards the camera |
| Back to the camera | a person photographed from behind |

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

Reading or writing was added from observed content. The remaining terms follow
the client's stated search cases.

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
| Iceberg | an iceberg floating in the sea |
| Exposed rock | bare rock without snow cover |
| Mountains | snow-covered mountains in the distance |
| Open water | open sea water |
| Coastline | a coastline where land meets the sea |
| Sunset | a sunset sky over the sea or mountains |
| Overcast or storm | heavy grey cloud or blowing snow |
| Clear sky | a clear blue sky |

Exposed rock is kept separate from snow. Several sample images show rock as the
dominant terrain, and collapsing this into a general snow term would lose it.

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
cable · gas cylinder · fuel drum · crate · detritus

### Living and domestic

stove · fire · heater · shelf · seat · chair · table · cupboard · bed · bunk ·
blanket · curtain · carpet · furniture · ladder

### Kitchen and provisions

food tin · food packet · jar · bottle · plate · cup · enamel bowl · tray ·
packaging · label

### Workshop and equipment

hand tool · hammer · saw · nail · paint tin · workbench · machinery ·
mechanical component · gauge · dial · compass · instrument

### Radio and electrical

radio set · headphones · wiring · switch panel · electrical component ·
antenna

### Clothing and personal

boots · footwear · jacket · clothing · glove · hat

### Paper and archive material

photograph · postcard · stamp · envelope · printed card · book · paper record ·
document · information panel · label · plaque

### Transport and vessels

ship · boat · sledge

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

## 13. Coverage in the sample

Client-listed terms checked against the 39 coded images.

| Group | Observed | Not observed in sample |
|---|---|---|
| Scenic | 5 of 10 | sunset, iceberg, water pool, storm, windy |
| People and activity | 3 of 11 | back of person, facing camera, singing, music, walking, cooking, sleeping, skiing |
| Outside structures and fittings | 8 of 20 | main hut, generator shed, emergency shed, anemometer tower, radio tower, gas canister, detritus, cement pillar, truss, beam, cement |
| Living room | 6 of 10 | fire, heater, cupboard, guitar |
| Kitchen | 3 of 6 | stove, food packet, cup |
| Workshop | 1 of 5 | paint tin, hammer, saw, nail |
| Bunkroom | 3 of 6 | jacket, flag, whale bone |
| Radio room | 3 of 6 | wiring, headphones, switch panel |

Absence from a 39-image sample does not mean absence from the archive of 1,008.
A targeted second pass is required to establish which terms are genuinely
unsupported by the collection, particularly for people and activity, where the
sample contains only four images with a person visible.

---

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

