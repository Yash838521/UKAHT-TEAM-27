const express = require('express')
const router  = express.Router()
const db      = require('../db')

// ── GET /api/categories — counts per category for home page cards ─────────────
router.get('/', async (req, res) => {
  try {
    // Extract primary category from JSON and count
    const [rows] = await db.query(`
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

    // Also get total image count and unprocessed count
    const [[totals]] = await db.query(`
      SELECT
        COUNT(*)                                          AS total_images,
        SUM(CASE WHEN processed = FALSE THEN 1 ELSE 0 END) AS pending
      FROM images
    `)

    res.json({
      categories:   rows,
      total_images: totals.total_images,
      pending:      totals.pending
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
