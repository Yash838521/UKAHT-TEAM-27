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
    const [[counts]] = await db.query(`
      SELECT
        COUNT(*)                                          AS total_images,
        SUM(a.is_verified)                               AS verified,
        AVG(q.overall_score)                             AS avg_quality,
        SUM(CASE WHEN e.gps_latitude IS NOT NULL THEN 1 ELSE 0 END) AS with_gps
      FROM images i
      LEFT JOIN ai_tags       a ON a.image_id = i.id
      LEFT JOIN quality_scores q ON q.image_id = i.id
      LEFT JOIN exif_metadata  e ON e.image_id = i.id
    `)

    const [perYear] = await db.query(`
      SELECT
        YEAR(e.date_taken) AS year,
        COUNT(*)           AS count
      FROM exif_metadata e
      WHERE e.date_taken IS NOT NULL
      GROUP BY YEAR(e.date_taken)
      ORDER BY year
    `)

    const [perSite] = await db.query(`
      SELECT
        COALESCE(
          JSON_UNQUOTE(JSON_EXTRACT(a.categories, '$[0].category')),
          'Unknown'
        ) AS site,
        COUNT(*) AS count
      FROM ai_tags a
      GROUP BY site
      ORDER BY count DESC
    `)

    res.json({
      total_images: counts.total_images,
      verified:     counts.verified,
      avg_quality:  counts.avg_quality,
      with_gps:     counts.with_gps,
      per_year:     perYear,
      per_site:     perSite
    })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/stats/accuracy
router.get('/accuracy', async (req, res) => {
  try {
    const [[row]] = await db.query(`
      SELECT
        COUNT(*)                                          AS total_reviewed,
        SUM(CASE WHEN c.id IS NOT NULL THEN 1 ELSE 0 END) AS corrected,
        AVG(a.scene_confidence)                           AS avg_confidence
      FROM ai_tags a
      LEFT JOIN corrections c ON c.image_id = a.image_id
      WHERE a.is_verified = TRUE
    `)
    res.json(row)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router