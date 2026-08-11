"""
UKAHT Mock Data Generator
Populates ai_tags, quality_scores, duplicate_clusters, embeddings,
categories, image_categories data, and upload_batches.
"""

import os
from dotenv import load_dotenv
import mysql.connector
import random
import json

# load .env
load_dotenv()

random.seed(42)

# Connect to MySQL
conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cursor = conn.cursor()

# Fetch all image IDs
cursor.execute("SELECT id FROM images ORDER BY id")
image_ids = [row[0] for row in cursor.fetchall()]

# Sanity check — ensures IDs are consistent across all team members
assert len(image_ids) == 1007, (
    f"Expected 1007 images but found {len(image_ids)}. "
    f"Re-run load_exif_metadata.py with the correct CSV before running this script."
)

print(f"Found {len(image_ids)} images — ID check passed")

# Realistic vocabularies
SCENE_TYPES = [
    ('exterior', 0.68),
    ('interior', 0.32),
]

OBJECT_VOCAB = [
    'tent', 'sledge', 'building', 'hut', 'flag', 'snow vehicle',
    'equipment', 'clothing', 'barrel', 'crate', 'rope', 'ladder',
    'food', 'scientific gear', 'camera', 'table', 'chair', 'bed',
    'stove', 'fuel drum', 'antenna', 'generator'
]

AI_MODELS = [
    'florence-2-base',
    'florence-2-large',
    'clip-vit-base-patch32'
]

VALID_CATEGORIES = [
    'Exterior', 'Interior', 'People', 'Equipment',
    'Camp life', 'Vehicles', 'Landscape', 'Unique only'
]

# Realistic mock captions — Florence-2 style descriptions
# Exterior captions
EXTERIOR_CAPTIONS = [
    "Two researchers standing outside a red tent in snowy conditions near the camp.",
    "An expedition member loading supplies onto a sledge beside the base hut.",
    "A group of people in heavy winter clothing gathered outside the camp buildings.",
    "A snow vehicle parked next to fuel drums at the Antarctic expedition base.",
    "An exterior view of the camp with flags visible against a grey overcast sky.",
    "A lone figure walking across a snow-covered landscape carrying equipment.",
    "Several sledges loaded with gear arranged outside the main camp building.",
    "Researchers working on scientific equipment in an open snow field.",
    "A tent pitched in the snow with mountains visible in the distance.",
    "Two people unloading crates from a snow vehicle near the fuel storage area.",
    "An aerial view of the expedition camp with multiple huts and antenna visible.",
    "A flag on a pole outside the main building with snow drifts in the background.",
]

# Interior captions
INTERIOR_CAPTIONS = [
    "Scientists reviewing data on laptops inside the dimly lit camp hut.",
    "A cluttered table with scientific instruments and food supplies inside the base.",
    "Two researchers examining samples under a microscope in the interior lab space.",
    "Camp beds and personal equipment arranged along the walls of the sleeping quarters.",
    "A stove with cooking equipment on a table inside the expedition hut.",
    "Scientific gear and clothing hanging from hooks in the interior of the base.",
    "A generator and electrical equipment in a utility room of the camp building.",
    "Researchers gathered around a table reviewing maps and expedition notes.",
    "A narrow corridor inside the base with ladders and equipment stored along the walls.",
    "Interior view of the kitchen area with food stores and cooking equipment visible.",
]

def get_caption(scene_type):
    """Return a realistic Florence-2 style caption based on scene type."""
    if scene_type == 'exterior':
        return random.choice(EXTERIOR_CAPTIONS)
    return random.choice(INTERIOR_CAPTIONS)

# Helper functions
def weighted_choice(choices):
    values, weights = zip(*choices)
    return random.choices(values, weights=weights, k=1)[0]

def realistic_scene_confidence(scene_type):
    if scene_type == 'exterior':
        return round(random.gauss(0.78, 0.14), 3)
    else:
        return round(random.gauss(0.65, 0.18), 3)

def realistic_people_count():
    distribution = [
        (0, 0.28),
        (1, 0.31),
        (2, 0.18),
        (3, 0.10),
        (4, 0.06),
        (5, 0.04),
        (6, 0.02),
        (8, 0.01),
    ]
    return weighted_choice(distribution)

def realistic_people_confidence(count):
    if count == 0:
        return round(random.gauss(0.71, 0.15), 3)
    elif count <= 2:
        return round(random.gauss(0.82, 0.10), 3)
    else:
        return round(random.gauss(0.58, 0.18), 3)

def realistic_tags(scene_type):
    exterior_tags = ['tent', 'sledge', 'flag', 'snow vehicle',
                     'building', 'hut', 'barrel', 'rope', 'equipment',
                     'fuel drum', 'antenna']
    interior_tags = ['table', 'chair', 'bed', 'stove', 'equipment',
                     'clothing', 'crate', 'camera', 'food',
                     'scientific gear', 'ladder', 'generator']

    pool   = exterior_tags if scene_type == 'exterior' else interior_tags
    n_tags = random.randint(2, 6)
    chosen = random.sample(pool, min(n_tags, len(pool)))

    tags = []
    for tag in chosen:
        if tag == chosen[0]:
            conf = round(random.uniform(0.70, 0.95), 3)
        else:
            conf = round(random.uniform(0.40, 0.85), 3)
        tags.append({'tag': tag, 'confidence': conf})

    if random.random() < 0.15:
        false_tag = random.choice(OBJECT_VOCAB)
        if false_tag not in [t['tag'] for t in tags]:
            tags.append({
                'tag': false_tag,
                'confidence': round(random.uniform(0.28, 0.45), 3)
            })

    return tags

def realistic_sharpness():
    r = random.random()
    if r < 0.12:
        return round(random.uniform(20, 80), 2)
    elif r < 0.30:
        return round(random.uniform(80, 200), 2)
    elif r < 0.75:
        return round(random.uniform(200, 500), 2)
    else:
        return round(random.uniform(500, 900), 2)

def realistic_exposure():
    r = random.random()
    if r < 0.10:
        return round(random.uniform(0.1, 0.3), 3)
    elif r < 0.22:
        return round(random.uniform(0.7, 0.95), 3)
    else:
        return round(random.uniform(0.35, 0.68), 3)

def overall_quality(sharpness, exposure):
    sharp_norm       = min(sharpness / 900, 1.0)
    exposure_penalty = 1 - (abs(exposure - 0.5) * 2)
    score            = (sharp_norm * 0.65) + (exposure_penalty * 0.35)
    return round(max(0, min(score, 1.0)), 3)

def mock_embedding():
    return [round(random.gauss(0, 0.3), 4) for _ in range(8)]

def build_categories(scene_type, people_count, tags):
    """
    Build categories JSON array from AI tag data.
    Stored directly in ai_tags.categories — no separate table needed.
    Returns list of category objects.
    Realistic: 1-3 categories per image, 10% noise.
    """
    tag_names    = [t['tag'] for t in tags]
    vehicle_tags = {'sledge', 'snow vehicle'}
    equip_tags   = {'equipment', 'scientific gear', 'antenna', 'generator', 'fuel drum'}
    camp_tags    = {'tent', 'hut', 'stove', 'food', 'bed', 'chair', 'table'}

    assignments = []

    if scene_type == 'exterior':
        assignments.append(('Exterior', round(random.uniform(0.65, 0.95), 3), True))
        if random.random() < 0.55:
            assignments.append(('Landscape', round(random.uniform(0.45, 0.80), 3), False))
    elif scene_type == 'interior':
        assignments.append(('Interior', round(random.uniform(0.60, 0.92), 3), True))

    if people_count and people_count > 0:
        conf = round(random.uniform(0.70, 0.95) if people_count >= 2 else random.uniform(0.55, 0.85), 3)
        assignments.append(('People', conf, False))

    if any(t in vehicle_tags for t in tag_names):
        assignments.append(('Vehicles', round(random.uniform(0.55, 0.88), 3), False))
    if any(t in equip_tags for t in tag_names):
        assignments.append(('Equipment', round(random.uniform(0.50, 0.85), 3), False))
    if any(t in camp_tags for t in tag_names):
        assignments.append(('Camp life', round(random.uniform(0.48, 0.82), 3), False))

    if random.random() < 0.10:
        noise = random.choice(VALID_CATEGORIES)
        if noise not in [a[0] for a in assignments]:
            assignments.append((noise, round(random.uniform(0.25, 0.45), 3), False))

    if not assignments:
        assignments.append(('Landscape', round(random.uniform(0.35, 0.55), 3), True))

    return [
        {
            'category':    cat,
            'confidence':  conf,
            'is_primary':  is_primary,
            'assigned_by': 'clip'
        }
        for cat, conf, is_primary in assignments
    ]


# STEP 1 — ai_tags (including categories JSON and caption)
print("\nStep 1: Populating ai_tags + categories + captions...")

failed_tagging = set(random.sample(image_ids, int(len(image_ids) * 0.15)))
ai_tag_map     = {}
ai_success     = 0

for image_id in image_ids:
    if image_id in failed_tagging:
        cursor.execute("""
            UPDATE ai_tags
            SET model_name = %s, is_verified = FALSE
            WHERE image_id = %s
        """, ('florence-2-base', image_id))
        continue

    scene_type   = weighted_choice(SCENE_TYPES)
    scene_conf   = max(0.1, min(realistic_scene_confidence(scene_type), 1.0))
    people_count = realistic_people_count()
    people_conf  = max(0.1, min(realistic_people_confidence(people_count), 1.0))
    tags         = realistic_tags(scene_type)
    model        = random.choice(AI_MODELS)
    is_verified  = random.random() < 0.08
    categories   = build_categories(scene_type, people_count, tags)
    caption      = get_caption(scene_type)

    cursor.execute("""
        UPDATE ai_tags SET
            scene_type        = %s,
            scene_confidence  = %s,
            people_count      = %s,
            people_confidence = %s,
            tags              = %s,
            categories        = %s,
            caption           = %s,
            model_name        = %s,
            is_verified       = %s
        WHERE image_id = %s
    """, (
        scene_type, scene_conf,
        people_count, people_conf,
        json.dumps(tags),
        json.dumps(categories),
        caption,
        model, is_verified,
        image_id
    ))

    ai_tag_map[image_id] = {
        'scene_type':   scene_type,
        'people_count': people_count,
        'tags':         tags,
        'categories':   categories,
        'caption':      caption
    }
    ai_success += 1

conn.commit()
print(f"  {ai_success} tagged with captions, {len(failed_tagging)} failed")


# STEP 2 — quality_scores
print("\nStep 2: Populating quality_scores...")

scores_by_image = {}
for image_id in image_ids:
    sharpness = realistic_sharpness()
    exposure  = realistic_exposure()
    overall   = overall_quality(sharpness, exposure)
    scores_by_image[image_id] = {
        'sharpness': sharpness,
        'exposure':  exposure,
        'overall':   overall
    }
    cursor.execute("""
        UPDATE quality_scores SET
            sharpness_score = %s,
            exposure_score  = %s,
            overall_score   = %s
        WHERE image_id = %s
    """, (sharpness, exposure, overall, image_id))

conn.commit()
print(f"  {len(image_ids)} quality scores populated")


# STEP 3 — duplicate_clusters
print("\nStep 3: Populating duplicate_clusters...")

remaining    = list(image_ids)
random.shuffle(remaining)
n_to_cluster = int(len(image_ids) * 0.12)
clustered    = []
cluster_id   = 1

while len(clustered) < n_to_cluster and len(remaining) >= 2:
    size_weights = [(2, 0.55), (3, 0.28), (4, 0.12), (5, 0.05)]
    size         = min(weighted_choice(size_weights), len(remaining))
    group        = remaining[:size]
    remaining    = remaining[size:]
    best_id      = max(group, key=lambda iid: scores_by_image[iid]['overall'])

    for img_id in group:
        is_rep    = (img_id == best_id)
        sim_score = 1.0 if is_rep else round(random.uniform(0.82, 0.99), 3)
        cursor.execute("""
            UPDATE duplicate_clusters SET
                cluster_id        = %s,
                cluster_type      = %s,
                similarity_score  = %s,
                is_representative = %s
            WHERE image_id = %s
        """, (cluster_id, 'phash', sim_score, is_rep, img_id))
        clustered.append(img_id)

    cluster_id += 1
    if len(clustered) >= n_to_cluster:
        break

conn.commit()
print(f"  {len(clustered)} images in {cluster_id - 1} duplicate clusters")
print(f"  {len(image_ids) - len(clustered)} images have no duplicates")

cursor.execute("""
    UPDATE quality_scores qs
    JOIN duplicate_clusters dc ON dc.image_id = qs.image_id
    SET qs.is_best_in_group = TRUE
    WHERE dc.is_representative = TRUE
""")
cursor.execute("""
    UPDATE quality_scores qs
    LEFT JOIN duplicate_clusters dc ON dc.image_id = qs.image_id
    SET qs.is_best_in_group = TRUE
    WHERE dc.cluster_id IS NULL
""")
conn.commit()
print("  is_best_in_group flags set")

# Add Unique only category to non-duplicate images
unique_cat_count = 0
cursor.execute("""
    SELECT image_id FROM duplicate_clusters
    WHERE cluster_id IS NULL OR is_representative = TRUE
""")
unique_ids = [row[0] for row in cursor.fetchall()]

for img_id in unique_ids:
    if img_id in failed_tagging:
        continue
    cursor.execute("SELECT categories FROM ai_tags WHERE image_id = %s", (img_id,))
    result = cursor.fetchone()
    if not result or not result[0]:
        continue
    cats     = json.loads(result[0])
    existing = [c['category'] for c in cats]
    if 'Unique only' not in existing:
        cats.append({
            'category':    'Unique only',
            'confidence':  round(random.uniform(0.75, 0.99), 3),
            'is_primary':  False,
            'assigned_by': 'hdbscan'
        })
        cursor.execute(
            "UPDATE ai_tags SET categories = %s WHERE image_id = %s",
            (json.dumps(cats), img_id)
        )
        unique_cat_count += 1

conn.commit()
print(f"  {unique_cat_count} images tagged as Unique only")


# STEP 4 — embeddings
print("\nStep 4: Populating embeddings...")

embedded = 0
for image_id in image_ids:
    if image_id in failed_tagging:
        continue
    cursor.execute("""
        UPDATE embeddings SET
            model_name = %s,
            embedding  = %s
        WHERE image_id = %s
    """, ('clip-vit-base-patch32', json.dumps(mock_embedding()), image_id))
    embedded += 1

conn.commit()
print(f"  {embedded} embeddings populated, {len(failed_tagging)} skipped")


# STEP 5 — corrections
print("\nStep 5: Adding sample human corrections...")

tagged_ids         = [iid for iid in image_ids if iid not in failed_tagging]
correction_samples = random.sample(tagged_ids, 12)

correction_examples = [
    ('scene_type',   'exterior', 'interior', 'staff_alice'),
    ('scene_type',   'interior', 'exterior', 'staff_bob'),
    ('people_count', '3',        '4',        'staff_alice'),
    ('people_count', '1',        '2',        'staff_bob'),
    ('scene_type',   'exterior', 'interior', 'staff_alice'),
    ('people_count', '0',        '1',        'staff_bob'),
    ('scene_type',   'interior', 'exterior', 'staff_alice'),
    ('people_count', '2',        '3',        'staff_bob'),
    ('scene_type',   'exterior', 'interior', 'staff_alice'),
    ('people_count', '4',        '3',        'staff_bob'),
    ('scene_type',   'interior', 'exterior', 'staff_alice'),
    ('people_count', '1',        '0',        'staff_bob'),
]

for image_id, (field, ai_val, human_val, reviewer) in zip(
    correction_samples, correction_examples
):
    cursor.execute("""
        INSERT INTO corrections
            (image_id, field_name, ai_value, human_value, reviewer)
        VALUES (%s, %s, %s, %s, %s)
    """, (image_id, field, ai_val, human_val, reviewer))
    cursor.execute("""
        UPDATE ai_tags SET is_verified = TRUE WHERE image_id = %s
    """, (image_id,))

conn.commit()
print("  12 corrections inserted across 2 reviewers")


# STEP 6 — upload_batches + link images to batches
print("\nStep 6: Populating upload_batches and linking images...")

STAFF_MEMBERS = ['staff_alice', 'staff_bob', 'staff_carol']

# Split all image IDs into mock batches of 5-20 images each
remaining_ids  = list(image_ids)
random.shuffle(remaining_ids)
batch_groups   = []

while remaining_ids:
    size  = random.randint(5, 20)
    group = remaining_ids[:size]
    remaining_ids = remaining_ids[size:]
    batch_groups.append(group)

# Create batches going back in time — newest first in DB
from datetime import datetime, timedelta

batch_count = 0
for i, group in enumerate(batch_groups):
    # Spread batches over the last 90 days
    days_ago     = int(i * (90 / max(len(batch_groups), 1)))
    uploaded_at  = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 8))
    uploaded_by  = random.choice(STAFF_MEMBERS)
    total_files  = len(group)
    # Simulate ~95% success rate
    failed       = sum(1 for _ in group if random.random() < 0.05)
    success      = total_files - failed

    cursor.execute("""
        INSERT INTO upload_batches
            (uploaded_by, uploaded_at, total_files, success, failed)
        VALUES (%s, %s, %s, %s, %s)
    """, (uploaded_by, uploaded_at, total_files, success, failed))

    batch_id = cursor.lastrowid

    # Link images to this batch
    for image_id in group:
        cursor.execute(
            "UPDATE images SET batch_id = %s WHERE id = %s",
            (batch_id, image_id)
        )

    batch_count += 1

conn.commit()
print(f"  {batch_count} batches created")
print(f"  {len(image_ids)} images linked to batches")


# FINAL SUMMARY
print("\nSummary")

cursor.execute("SELECT COUNT(*) FROM ai_tags WHERE scene_type IS NOT NULL")
print(f"ai_tags populated:              {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ai_tags WHERE scene_type IS NULL")
print(f"ai_tags failed/empty:           {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ai_tags WHERE categories IS NOT NULL")
print(f"images with categories:         {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ai_tags WHERE caption IS NOT NULL")
print(f"images with captions:           {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM quality_scores WHERE overall_score IS NOT NULL")
print(f"quality_scores populated:       {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM duplicate_clusters WHERE cluster_id IS NOT NULL")
print(f"images in duplicate clusters:   {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(DISTINCT cluster_id) FROM duplicate_clusters WHERE cluster_id IS NOT NULL")
print(f"total duplicate clusters:       {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM embeddings WHERE embedding IS NOT NULL")
print(f"embeddings populated:           {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM corrections")
print(f"human corrections logged:       {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ai_tags WHERE is_verified = TRUE")
print(f"images verified by staff:       {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM upload_batches")
print(f"upload batches created:         {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM images WHERE batch_id IS NOT NULL")
print(f"images linked to batches:       {cursor.fetchone()[0]}")

cursor.close()
conn.close()
print("\nDone — database ready for frontend and middleware development.")