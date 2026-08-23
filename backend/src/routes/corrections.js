const express = require('express')
const router  = express.Router()
const db      = require('../db')

// GET /api/corrections/queue — uncertainty-ordered review queue
router.get('/queue', async (req, res) => {
  try {
    const { limit = 20, page = 1 } = req.query
    const offset = (Number(page) - 1) * Number(limit)

    const [rows] = await db.query(`
      SELECT
        i.id, i.filename, i.storage_url,
        a.scene_type, a.scene_confidence,
        a.people_count, a.people_confidence,
        a.tags, a.categories, a.is_verified,
        a.model_name,
        a.uncertainty_score, a.uncertainty_reason, a.review_recommended
      FROM images i
      JOIN ai_tags a ON a.image_id = i.id
      WHERE a.is_verified = FALSE
        AND a.review_recommended = TRUE
      ORDER BY a.uncertainty_score DESC
      LIMIT ? OFFSET ?
    `, [Number(limit), offset])

    const [[{ total }]] = await db.query(`
      SELECT COUNT(*) AS total
      FROM ai_tags
      WHERE is_verified = FALSE
        AND review_recommended = TRUE
    `)

    res.json({ total, page: Number(page), images: rows })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/corrections/:imageId
router.get('/:imageId', async (req, res) => {
  try {
    const [rows] = await db.query(
      `SELECT * FROM corrections WHERE image_id = ? ORDER BY corrected_at DESC`,
      [req.params.imageId]
    )
    res.json(rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// POST /api/corrections
router.post('/', async (req, res) => {
  try {
    const { image_id, field_name, ai_value, human_value, reviewer } = req.body

    if (!image_id || !field_name || !human_value) {
      return res.status(400).json({ error: 'image_id, field_name and human_value are required' })
    }

    await db.query(
      `INSERT INTO corrections (image_id, field_name, ai_value, human_value, reviewer)
       VALUES (?, ?, ?, ?, ?)`,
      [image_id, field_name, ai_value, human_value, reviewer || 'unknown']
    )

    await db.query(
      `UPDATE ai_tags SET is_verified = TRUE WHERE image_id = ?`,
      [image_id]
    )

    res.status(201).json({ message: 'Correction saved successfully' })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// POST /api/corrections/confirm
router.post('/confirm', async (req, res) => {
  try {
    const { image_id, reviewer } = req.body
    if (!image_id) return res.status(400).json({ error: 'image_id is required' })

    await db.query(
      `UPDATE ai_tags SET is_verified = TRUE WHERE image_id = ?`,
      [image_id]
    )

    res.json({ message: 'Image confirmed as verified' })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router