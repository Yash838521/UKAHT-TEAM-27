const express = require('express')
const router  = express.Router()
const db      = require('../db')

// GET /api/stats/tags — tag counts grouped by facet
router.get('/tags', async (req, res) => {
  try {
    const [rows] = await db.query(`
      SELECT
        jt.tag,
        jt.facet,
        COUNT(*) AS count
      FROM ai_tags a
      JOIN JSON_TABLE(
        a.tags,
        '$[*]' COLUMNS (
          tag   VARCHAR(100) PATH '$.tag',
          facet VARCHAR(50)  PATH '$.facet'
        )
      ) AS jt
      WHERE jt.tag IS NOT NULL
      GROUP BY jt.facet, jt.tag
      ORDER BY jt.facet, count DESC
    `)
    res.json(rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/stats/dataset
router.get('/dataset', async (req, res) => {
  try {
    // Total images
    const [[{ total_images }]] = await db.query(`
      SELECT COUNT(*) AS total_images FROM images
    `)

    const [[duplicates]] = await db.query(`
      SELECT
        COUNT(DISTINCT image_id)                              AS in_clusters,
        COUNT(DISTINCT CONCAT(cluster_type, ':', cluster_id))  AS total_clusters
      FROM duplicate_clusters
      WHERE cluster_type IN ('phashing', 'clip_embedding')
    `)

    // Verification — how many images have been AI tagged, and how many of those verified
    const [[verification]] = await db.query(`
      SELECT
        COUNT(*)                                    AS total_tagged,
        SUM(CASE WHEN is_verified THEN 1 ELSE 0 END) AS verified
      FROM ai_tags
    `)

    // Scene type breakdown
    const [scene_types] = await db.query(`
      SELECT scene_type, COUNT(*) AS count
      FROM ai_tags
      WHERE scene_type IS NOT NULL
      GROUP BY scene_type
      ORDER BY count DESC
    `)

    // Quality buckets
    const [[quality]] = await db.query(`
      SELECT
        SUM(CASE WHEN overall_score >= 0.70 THEN 1 ELSE 0 END)                          AS high,
        SUM(CASE WHEN overall_score >= 0.40 AND overall_score < 0.70 THEN 1 ELSE 0 END) AS medium,
        SUM(CASE WHEN overall_score < 0.40 THEN 1 ELSE 0 END)                           AS low
      FROM quality_scores
    `)

    // Metadata completeness — measured against all images, not just ones with exif rows
    const [[completeness]] = await db.query(`
      SELECT
        COUNT(*)                                                           AS total,
        SUM(CASE WHEN e.date_taken    IS NOT NULL THEN 1 ELSE 0 END)      AS has_date,
        SUM(CASE WHEN e.camera_model  IS NOT NULL THEN 1 ELSE 0 END)      AS has_camera,
        SUM(CASE WHEN e.gps_latitude  IS NOT NULL THEN 1 ELSE 0 END)      AS has_gps
      FROM images i
      LEFT JOIN exif_metadata e ON e.image_id = i.id
    `)

    // Top cameras
    const [cameras] = await db.query(`
      SELECT camera_model, camera_make, COUNT(*) AS count
      FROM exif_metadata
      WHERE camera_model IS NOT NULL
      GROUP BY camera_model, camera_make
      ORDER BY count DESC
      LIMIT 20
    `)

    // People distribution
    const [people_dist] = await db.query(`
      SELECT people_count, COUNT(*) AS count
      FROM ai_tags
      WHERE people_count IS NOT NULL
      GROUP BY people_count
      ORDER BY people_count
    `)

    // Images per year
    const [per_year] = await db.query(`
      SELECT YEAR(e.date_taken) AS year, COUNT(*) AS count
      FROM exif_metadata e
      WHERE e.date_taken IS NOT NULL
      GROUP BY YEAR(e.date_taken)
      ORDER BY year
    `)

    res.json({
      total_images,
      duplicates,
      verification,
      scene_types,
      quality,
      completeness,
      cameras,
      people_dist,
      per_year
    })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/stats/accuracy
router.get('/accuracy', async (req, res) => {
  try {
    const [[{ total_corrections }]] = await db.query(`
      SELECT COUNT(*) AS total_corrections FROM corrections
    `)

    const [per_field] = await db.query(`
      SELECT field_name, COUNT(*) AS corrections
      FROM corrections
      GROUP BY field_name
      ORDER BY corrections DESC
    `)

    const [scene_accuracy] = await db.query(`
      SELECT ai_value AS predicted, human_value AS actual, COUNT(*) AS count
      FROM corrections
      WHERE field_name = 'scene_type'
      GROUP BY ai_value, human_value
      ORDER BY count DESC
    `)

    const [[{ people_mae }]] = await db.query(`
      SELECT AVG(ABS(CAST(ai_value AS SIGNED) - CAST(human_value AS SIGNED))) AS people_mae
      FROM corrections
      WHERE field_name = 'people_count'
        AND ai_value    REGEXP '^-?[0-9]+$'
        AND human_value REGEXP '^-?[0-9]+$'
    `)

    res.json({
      total_corrections,
      per_field,
      scene_accuracy,
      people_mae
    })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router