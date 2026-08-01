const express = require('express')
const router  = express.Router()
const db      = require('../db')

// ── GET /api/stats/dataset — full dataset statistical report ──────────────────
router.get('/dataset', async (req, res) => {
  try {

    // Total images
    const [[{ total_images }]] = await db.query(
      `SELECT COUNT(*) AS total_images FROM images`
    )

    // Images per year
    const [per_year] = await db.query(`
      SELECT YEAR(date_taken) AS year, COUNT(*) AS count
      FROM exif_metadata
      WHERE date_taken IS NOT NULL
      GROUP BY YEAR(date_taken)
      ORDER BY year
    `)

    // Camera model breakdown
    const [cameras] = await db.query(`
      SELECT camera_model, camera_make, COUNT(*) AS count
      FROM exif_metadata
      WHERE camera_model IS NOT NULL
      GROUP BY camera_model, camera_make
      ORDER BY count DESC
    `)

    // Scene type split
    const [scene_types] = await db.query(`
      SELECT
        COALESCE(c.human_value, a.scene_type) AS scene_type,
        COUNT(*) AS count
      FROM ai_tags a
      LEFT JOIN corrections c ON c.image_id = a.image_id AND c.field_name = 'scene_type'
      WHERE a.scene_type IS NOT NULL
      GROUP BY scene_type
    `)

    // People count distribution
    const [people_dist] = await db.query(`
      SELECT
        COALESCE(c.human_value, a.people_count) AS people_count,
        COUNT(*) AS count
      FROM ai_tags a
      LEFT JOIN corrections c ON c.image_id = a.image_id AND c.field_name = 'people_count'
      WHERE a.people_count IS NOT NULL
      GROUP BY people_count
      ORDER BY people_count
    `)

    // Metadata completeness
    const [[completeness]] = await db.query(`
      SELECT
        COUNT(*)                                                    AS total,
        SUM(CASE WHEN date_taken    IS NOT NULL THEN 1 ELSE 0 END) AS has_date,
        SUM(CASE WHEN camera_model  IS NOT NULL THEN 1 ELSE 0 END) AS has_camera,
        SUM(CASE WHEN gps_latitude  IS NOT NULL THEN 1 ELSE 0 END) AS has_gps
      FROM exif_metadata
    `)

    // Quality distribution
    const [[quality]] = await db.query(`
      SELECT
        SUM(CASE WHEN overall_score >= 0.7                        THEN 1 ELSE 0 END) AS high,
        SUM(CASE WHEN overall_score >= 0.4 AND overall_score < 0.7 THEN 1 ELSE 0 END) AS medium,
        SUM(CASE WHEN overall_score <  0.4                        THEN 1 ELSE 0 END) AS low
      FROM quality_scores
      WHERE overall_score IS NOT NULL
    `)

    // Duplicate rate
    const [[duplicates]] = await db.query(`
      SELECT
        COUNT(*)                                                         AS total,
        SUM(CASE WHEN cluster_id IS NOT NULL THEN 1 ELSE 0 END)        AS in_clusters,
        COUNT(DISTINCT cluster_id)                                       AS total_clusters
      FROM duplicate_clusters
    `)

    // Category breakdown
    const [categories] = await db.query(`
      SELECT
        JSON_UNQUOTE(JSON_EXTRACT(cat.value, '$.category')) AS category,
        COUNT(*) AS count
      FROM ai_tags,
      JSON_TABLE(categories, '$[*]' COLUMNS (
        value JSON PATH '$'
      )) AS cat
      WHERE JSON_EXTRACT(cat.value, '$.is_primary') = true
        AND categories IS NOT NULL
      GROUP BY category
      ORDER BY count DESC
    `)

    // AI verification rate
    const [[verification]] = await db.query(`
      SELECT
        COUNT(*)                                              AS total_tagged,
        SUM(CASE WHEN is_verified = TRUE THEN 1 ELSE 0 END) AS verified
      FROM ai_tags
      WHERE scene_type IS NOT NULL
    `)

    res.json({
      total_images,
      per_year,
      cameras,
      scene_types,
      people_dist,
      completeness,
      quality,
      duplicates,
      categories,
      verification
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── GET /api/stats/accuracy — AI tag accuracy vs human corrections ────────────
router.get('/accuracy', async (req, res) => {
  try {
    // Overall correction count
    const [[overall]] = await db.query(`
      SELECT COUNT(*) AS total_corrections FROM corrections
    `)

    // Corrections per field
    const [per_field] = await db.query(`
      SELECT field_name, COUNT(*) AS corrections
      FROM corrections
      GROUP BY field_name
    `)

    // Scene type accuracy (where corrected)
    const [scene_accuracy] = await db.query(`
      SELECT
        c.ai_value    AS predicted,
        c.human_value AS actual,
        COUNT(*)      AS count
      FROM corrections c
      WHERE c.field_name = 'scene_type'
      GROUP BY c.ai_value, c.human_value
    `)

    // People count mean absolute error
    const [[people_mae]] = await db.query(`
      SELECT AVG(ABS(CAST(c.ai_value AS SIGNED) - CAST(c.human_value AS SIGNED))) AS mae
      FROM corrections c
      WHERE c.field_name = 'people_count'
    `)

    res.json({
      total_corrections: overall.total_corrections,
      per_field,
      scene_accuracy,
      people_mae:        people_mae.mae
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
