# Controlled Vocabulary Design and Threshold Calibration

---

## 1. Introduction

The UK Antarctic Heritage Trust archive comprises 1,008 photographs across
three Antarctic sites, spanning 2009 to 2024. Technical metadata is close to
complete: capture date is present on 94.6% of images and camera details on
94.5%. Descriptive metadata is effectively absent. Six images carry keywords,
nine name a photographer and three record copyright. Retrieval is therefore
manual, and does not scale.

The system addresses this by generating descriptive metadata automatically using
vision-language models. Automatic description alone, however, does not produce a
searchable archive. A model that writes free text for each image produces prose
that cannot populate a filter, cannot be scored for accuracy, and cannot be
compared against human judgement. Structure is required first.

This chapter covers the component that supplies that structure: a controlled
vocabulary of terms applied to every image, and the calibration of the
confidence thresholds that govern when each term is assigned.

Three contributions are reported:

1. A faceted vocabulary of 165 terms, derived from the archive and the client's
   stated retrieval needs, and validated against images not used in its
   construction.
2. A threshold calibration procedure that improves assignment quality over the
   uniform value used in the initial pipeline.
3. A cross-validated estimate of that improvement, establishing how much of the
   apparent gain is attributable to fitting rather than to genuine effect.

---

## 2. Background and rationale

### 2.1 Why a controlled vocabulary is required

Three downstream components depend on a fixed term set.

**Measurement.** Model performance is scored by comparing assigned terms with
human-assigned terms. Free-text description makes agreement incomputable: two
annotators describing the same photograph as "shed" and "outbuilding" cannot be
recognised as agreeing, and a model producing either cannot be scored.

**Annotation consistency.** The reference set used for evaluation is labelled by
multiple people. Without a fixed list, each produces an incompatible
description.

**Retrieval.** Filters in the user interface are the vocabulary made visible.
Every facet in the interface corresponds to a facet defined here.

The vocabulary is additionally a contracted deliverable. The client's stated
requirements specify that the descriptive terms chosen must be maintained and
supplied as project documentation.

### 2.2 Why threshold calibration is required

Terms are assigned by comparing an image embedding with a text embedding of each
term's prompt, and accepting terms whose cosine similarity exceeds a threshold.
The initial pipeline applied a single value of 0.24 to every facet.

A uniform threshold is unlikely to be optimal. Similarity values produced by
contrastive vision-language models are not calibrated probabilities and are not
comparable across prompt sets that differ in length, specificity and semantic
breadth. A prompt describing a narrow visual property and one describing a broad
scene category occupy different regions of the similarity distribution.

Evidence of miscalibration was visible in the initial output. The term
`object_wear` was assigned to 504 of 1,006 images, `partial_person` to 81 against
19 for `person_alone`, and `glacier` was the most frequently assigned nature term
at 141 occurrences in an archive predominantly composed of building photography.
Each is consistent with a threshold set too permissively for that facet.

---

## 3. Vocabulary construction

### 3.1 Sampling

Terms were derived from a stratified sample rather than proposed in the
abstract, so that the resulting list reflects the archive's actual content.

The archive is organised into ten directories of markedly unequal size, ranging
from 3 to 385 images. Four images were drawn from each directory, giving 39.
Selection used a fixed random seed, making the sample exactly reproducible and
demonstrating that images were not chosen selectively.

Equal allocation was preferred to proportional allocation. Proportional sampling
would have drawn approximately fifteen images from the largest artefact
collection and one from the smallest historic collection, producing terms
describing artefact photography in detail and other material poorly.

### 3.2 Open coding

Each sampled image was described in free text across seven fields: subject,
objects present, setting, people present, condition, candidate terms, and notes.

Categorisation was deliberately deferred. Establishing categories during the
early images would have caused later images to be forced into categories chosen
before the range of content was known. This produced 111 distinct candidate terms
across 227 mentions, of which 72 occurred once.

Ten of the 39 descriptions were subsequently re-examined against the images to
confirm that recorded settings and named objects were accurate. All ten were
confirmed.

### 3.3 Reduction and exclusion

Seven frequently occurring terms were removed: heritage, conservation,
documentation, historic, museum, Antarctic and artefact.

Each applies to substantially every image in the archive. A term matching all
records cannot reduce a result set and therefore has no retrieval value,
irrespective of how naturally it arises in description. "Heritage" was the third
most frequent term in the coding pass and was excluded on this basis.

This distinction — between terms that describe an archive and terms that
discriminate within it — is the central design principle of the vocabulary.

### 3.4 Facet structure

A single label per image cannot express the client's stated retrieval needs,
which combine site, room, object, condition and photographic treatment. Terms are
therefore organised into ten facets, each contributing independently.

| Facet | Values per image | Derivation |
|---|---|---|
| Site | One | Directory path |
| Scene type | One | Image content |
| Room | One, interiors only | Image content |
| Structure | Any, exteriors only | Image content |
| People | One | Image content |
| Orientation | Any | Image content |
| Activity | Any | Image content |
| Nature and wildlife | Any | Image content |
| Condition | Any | Image content |
| Shot type | One | Image content |
| Object tags | Any | Image content |

Site is derived from directory naming rather than from image content. Coordinates
are present on 6.3% of images; site is derivable for 100%, making the derived
field the more useful geographic dimension by a wide margin.

The client's requirements named three sites present in the supplied data, and
five further sites for which no images were supplied. Terms for all eight are
retained so that the system accommodates future material.

---

## 4. Vocabulary validation

### 4.1 Method

A vocabulary fits the sample from which it was derived by construction. Whether
it generalises is a separate question, and was tested directly.

A second sample of 27 images was drawn using a different random seed, excluding
every image used during derivation. Terms were assigned using only the published
list. Where no term applied, the facet was left empty and the required term
recorded; where two terms both applied, the difficulty was recorded.

### 4.2 Coverage

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

All three mandatory facets achieved complete coverage. Room achieved complete
coverage on applicable images. The optional facets reflect image content rather
than deficiencies in the term set: three images contained a person, which bounds
activity and orientation coverage at three.

Of the 83 available object tags, 41 were applied. Terms per image ranged from 4
to 17, with a mean of 9.4.

### 4.3 Scene distribution

| Scene type | Images |
|---|---|
| Object study | 9 |
| Exterior | 7 |
| Landscape | 6 |
| Interior | 5 |

Object study was introduced during derivation to accommodate three images that
could be classified as neither interior nor exterior: single objects photographed
against plain backgrounds with the surrounding context deliberately excluded. In
validation it proved the largest single category. A term introduced to resolve an
edge case describes a third of independently sampled material.

### 4.4 Revisions

| Change | Evidence |
|---|---|
| Added `side_on` to orientation | Two images showed a person in profile; neither existing term applied |
| Added `mixed_orientation` | One group photograph showed people facing several directions |
| Added `resting` to activity | A group image showed people at ease rather than posing |
| Added `glacier` to nature | An ice formation could not be resolved as iceberg or ice cliff |
| Added `rope`, `cabinet`, `flask`, `ruler`, `instrument case` | Recorded as required but unavailable during annotation |
| Added a containers group | Labelled cases and boxes had no suitable term |
| Clarified the exterior and landscape boundary | An outdoor image containing a sledge and wildlife but no building fell between the definitions |

The vocabulary moved from 150 to 165 terms at version 1.0.

### 4.5 Structure identification

Four of six exterior images were recorded as `outbuilding` because building
identity could not be established from the photograph. The terms
`generator_shed`, `emergency_shed`, `anemometer_tower` and `radio_tower` were
applied to no image.

Small outbuildings at these sites are of similar construction and are not
visually distinguishable. Reliable assignment requires site maps identifying
which building occupies which position. These were requested from the client and
were not available.

This is reported as a measured limitation rather than an assumption. The terms
are retained so that the system accommodates the maps if they become available,
and images receive `outbuilding` in the interim.

### 4.6 Ambiguity

Sixteen of 27 images carried a note recording a difficult decision. These divide
into two categories.

The majority record a refusal to infer beyond visible evidence: building identity
not determinable, garment type unclear, ice formation indeterminate. This is the
intended annotation behaviour.

Two record genuine overlap between terms, both concerning the boundary between
`radio_room` and `museum_display` where a room containing radio equipment is also
arranged for public interpretation. A precedence rule was introduced.

Ambiguity was recorded deliberately: points at which one annotator hesitates are
points at which two annotators would disagree. Resolving them before group
annotation reduces inconsistency in the reference set.

---

## 5. Threshold calibration

### 5.1 Procedure

Assignment quality was measured against the 27 annotated images. For each facet,
similarity was computed between every image embedding and every term prompt, and
threshold values from 0.15 to 0.40 in steps of 0.002 were evaluated. The value
maximising micro-averaged F1 was selected.

Facets are handled according to their cardinality. Scene type and shot type
always assign the highest-scoring term and are reported as accuracy. People and
room apply a threshold with a fallback term where no term exceeds it. The
remaining facets accept every term above the threshold.

### 5.2 Embedding alignment verification

Image embeddings were produced under transformers 4.45.2; text embeddings were
produced under version 5.15.0, in which the text feature interface changed.

Two silent failures arose during implementation and are reported because both
produced complete, plausible output tables.

In the first, the text feature call returned a model output object rather than a
tensor. Extracting the pooled hidden state instead of the projected embedding
produced vectors of the correct dimensionality — both are 512-wide for this model
— but in a different representational space. All similarity values fell below
0.16, every threshold facet returned an F1 of zero, and the people facet returned
0.889 solely by falling back to `no_people` on all 27 images.

In the second, a cached prompt file was written relative to one working directory
and deleted relative to another. Two subsequent runs consumed stale vectors
without indicating that a cache was in use.

Neither raised an exception. Both were detected only through explicit
verification: recomputing the assignments in the existing tag file and requiring
them to match, and checking that similarity values fall within a plausible range.

Following correction, recomputed assignments matched the original pipeline on
1,006 of 1,006 images for both scene type and shot type, and the maximum observed
similarity of 0.3561 matched the maximum in the original output to four decimal
places. Alignment was thereby established empirically rather than assumed.

Both verification steps were retained in the calibration module.

### 5.3 Calibration results

| Facet | Support | Uniform F1 | Calibrated F1 | Threshold | Change |
|---|---|---|---|---|---|
| Activity | 3 | 0.364 | 0.800 | 0.260 | +0.436 |
| Orientation | 1 | 0.000 | 0.200 | 0.196 | +0.200 |
| Nature | 50 | 0.320 | 0.492 | 0.212 | +0.172 |
| Structure | 6 | 0.348 | 0.462 | 0.266 | +0.114 |
| Condition | 27 | 0.450 | 0.500 | 0.232 | +0.050 |
| People | 27 | 0.963 | 0.963 | 0.232 | 0.000 |
| Room | 5 | 0.800 | 0.800 | 0.226 | 0.000 |
| **Mean** | | **0.463** | **0.602** | | **+0.139** |

Scene type achieved 85.2% accuracy and shot type 59.3% under argmax assignment,
neither being threshold-dependent.

---

## 6. Cross-validated estimation

### 6.1 Rationale

The thresholds in section 5.3 were selected using the same 27 images on which
they were then measured. This produces an optimistic estimate, because the
selected value partly reflects the particular sample rather than the underlying
behaviour of the model.

Leave-one-out cross-validation separates selection from measurement. For each
image, the threshold is chosen using the remaining 26 and applied to the held-out
image. Every measurement therefore derives from data that took no part in
selection. With 27 images this is the appropriate resampling method, since it
sacrifices no data to a held-out partition.

### 6.2 Results

| Facet | Folds | Support | Threshold | SD | Precision | Recall | F1 | Fitted F1 | Optimism | Honest gain |
|---|---|---|---|---|---|---|---|---|---|---|
| People | 27 | 27 | 0.233 | 0.003 | 0.926 | 0.926 | 0.926 | 0.963 | 0.037 | −0.037 |
| Room | 5 | 5 | 0.211 | 0.030 | 0.600 | 0.600 | 0.600 | 0.800 | 0.200 | −0.200 |
| Structure | 7 | 6 | 0.262 | 0.010 | 0.273 | 0.500 | 0.353 | 0.462 | 0.109 | +0.005 |
| Orientation | 3 | 1 | 0.179 | 0.020 | 0.091 | 1.000 | 0.167 | 0.200 | 0.033 | +0.167 |
| Activity | 3 | 3 | 0.260 | 0.000 | 1.000 | 0.667 | 0.800 | 0.800 | 0.000 | +0.436 |
| Nature | 27 | 50 | 0.212 | 0.001 | 0.392 | 0.580 | 0.468 | 0.492 | 0.024 | +0.148 |
| Condition | 27 | 27 | 0.231 | 0.003 | 0.522 | 0.444 | 0.480 | 0.500 | 0.020 | +0.030 |
| **Mean** | | | | | | | **0.542** | **0.602** | **0.060** | **+0.078** |

Mean F1 rises from 0.463 under the uniform threshold to 0.542 under
cross-validated calibration, a gain of 0.078. The fitted estimate was 0.139.
Approximately 44% of the apparent improvement was therefore attributable to
fitting rather than to genuine effect.

### 6.3 Threshold stability

The standard deviation of the threshold selected across folds indicates whether a
value reflects a stable property of the facet or is driven by individual images.

| Facet | Threshold | SD as proportion | Reading |
|---|---|---|---|
| Activity | 0.260 | 0.0% | Stable |
| Nature | 0.212 | 0.5% | Stable |
| People | 0.233 | 1.3% | Stable |
| Condition | 0.231 | 1.3% | Stable |
| Structure | 0.262 | 3.8% | Moderate variation |
| Orientation | 0.179 | 11.2% | Unstable |
| Room | 0.211 | 14.2% | Unstable |

Stability corresponds closely to annotation support. The four facets with the
most stable thresholds include the three with the largest support. The two
unstable facets have support of five and one respectively.

This provides an evidenced basis for expanding the reference set, and identifies
which facets require it.

### 6.4 Facets where calibration was detrimental

Calibration reduced performance on two facets. People fell from 0.963 to 0.926
and room from 0.800 to 0.600.

In both, the uniform value of 0.24 was already close to optimal, and the sweep
selected a value fitted to noise in the small sample. Room, with five annotated
images and the least stable threshold, is the clearest case.

This is reported rather than omitted. A calibration procedure applied
indiscriminately does not uniformly improve performance, and the conditions under
which it fails are as informative as those under which it succeeds.

### 6.5 Recommended policy

The evidence supports selective rather than universal calibration.

| Facet | Recommendation | Basis |
|---|---|---|
| Nature | Calibrate to 0.212 | Largest support, most stable threshold, +0.148 |
| Condition | Calibrate to 0.231 | Adequate support, stable, +0.030 |
| Activity | Calibrate to 0.260 | Zero optimism, though support is limited |
| People | Retain 0.240 | Calibration measurably detrimental |
| Room | Retain 0.240 | Calibration detrimental, threshold unstable |
| Structure | Suspend | Insufficient support; terms untestable without site maps |
| Orientation | Suspend | Single annotation; result not interpretable |

---

## 7. Limitations

**Reference set size.** Terms were derived from 39 images and calibrated on 27,
from an archive of 1,008. Absence of a term from the reference set does not
establish absence from the archive.

**Annotation support.** Only nature, condition and people have sufficient
annotation for reliable calibration. Orientation has one positive instance and
activity three; thresholds for these facets are not interpretable.

**Single annotator.** The reference set was produced by one annotator, so no
inter-annotator agreement coefficient is available. Reliability testing is
deferred to the larger ground-truth set.

**Structure facet untested.** Four terms could not be evaluated for the reason
given in section 4.5.

**Sites unrepresented.** The client names eight sites; the supplied data contains
images from three. Terms for the remainder are held but untested, and directory
markers for three are unknown.

**Library version divergence.** Image and text embeddings were produced under
different transformers versions. Alignment was verified empirically, but pinning
a single version across the pipeline would be preferable.

---

## 8. Conclusions

A faceted controlled vocabulary of 165 terms was derived from the archive and the
client's stated requirements, and validated against images not used in its
construction. All mandatory facets achieved complete coverage on the validation
sample, and nine terms were added on the basis of identified gaps.

Threshold calibration improved mean F1 from 0.463 to 0.602 when selection and
measurement were performed on the same data. Leave-one-out cross-validation
established a corrected estimate of 0.542, indicating that 44% of the apparent
improvement was attributable to fitting. The corrected gain of 0.078 is
attributable to calibration.

Calibration was not uniformly beneficial. Two facets performed worse under
calibrated thresholds, and the analysis identifies threshold stability across
folds as a practical indicator distinguishing facets where calibration transfers
from those where it does not.

Two silent failure modes were encountered during implementation, neither of which
raised an error and both of which produced complete output tables. They were
detected only through explicit verification against known-correct results. The
verification steps were retained in the delivered module.

---

## Appendix A: Artefacts

| Item | Location |
|---|---|
| Vocabulary specification | `docs/vocabulary.md` |
| Machine-readable vocabulary | `pipeline/src/ukaht/tagging/vocabulary.py` |
| Vocabulary tests | `pipeline/tests/test_vocabulary.py` |
| Sample selection | `pipeline/src/ukaht/tagging/viewing_sample.py` |
| Coding note consolidation | `pipeline/src/ukaht/tagging/coding_notes.py` |
| Validation and coverage analysis | `pipeline/src/ukaht/tagging/validation.py` |
| Annotation consolidation | `pipeline/src/ukaht/tagging/merge_annotations.py` |
| Threshold calibration | `pipeline/src/ukaht/tagging/calibration.py` |
| Cross-validated estimation | `pipeline/src/ukaht/tagging/cross_validation.py` |
| Calibration results | `evaluation/results/threshold_calibration.csv` |
| Threshold sweep | `evaluation/results/threshold_sweep.csv` |
| Cross-validation results | `evaluation/results/threshold_cross_validation.csv` |

The vocabulary carries 88 automated tests covering internal consistency, facet
structure, exclusion enforcement, and the presence of every term named in the
client's requirements.

Annotation records and images are held outside version control.

## Appendix B: Reproduction

Vocabulary summary and validation:

```
python -m ukaht.tagging.validation report --sheet <annotation sheet>
```

Threshold calibration:

```
python -m ukaht.tagging.calibration \
  --index <clip index> --embeddings <clip embeddings> \
  --annotations <annotation sheet> --manifest <sample manifest> \
  --verify-against <existing tag file>
```

Cross-validated estimation:

```
python -m ukaht.tagging.cross_validation \
  --index <clip index> --embeddings <clip embeddings> \
  --annotations <annotation sheet> --manifest <sample manifest>
```

Sample selection uses fixed seeds: 27 for the derivation sample and 91 for the
validation sample.