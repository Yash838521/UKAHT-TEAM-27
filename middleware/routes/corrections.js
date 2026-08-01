const express = require('express')
const router  = express.Router()
const db      = require('../db')

// ── GET /api/corrections/queue — low confidence images for review ─────────────
router.get('/queue', async (req, res) => {
  try {
    const { limit = 20, page = 1 } = req.query
    const offset = (Number(page) - 1) * Number(limit)

    // Return images where AI confidence is low or not yet verified
    const [rows] = await db.query(`
      SELECT
        i.id, i.filename, i.storage_url,
        a.scene_type, a.scene_confidence,
        a.people_count, a.people_confidence,
        a.tags, a.categories, a.is_verified,
        a.model_name
      FROM images i
      JOIN ai_tags a ON a.image_id = i.id
      WHERE a.is_verified = FALSE
        AND a.scene_type IS NOT NULL
        AND (
          a.scene_confidence  < 0.70 OR
          a.people_confidence < 0.65
        )
      ORDER BY a.scene_confidence ASC
      LIMIT ? OFFSET ?
    `, [Number(limit), offset])

    const [[{ total }]] = await db.query(`
      SELECT COUNT(*) AS total
      FROM ai_tags
      WHERE is_verified = FALSE
        AND scene_type IS NOT NULL
        AND (scene_confidence < 0.70 OR people_confidence < 0.65)
    `)

    res.json({ total, page: Number(page), images: rows })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── GET /api/corrections/:imageId — get all corrections for one image ─────────
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

// ── POST /api/corrections — submit a correction ───────────────────────────────
router.post('/', async (req, res) => {
  try {
    const { image_id, field_name, ai_value, human_value, reviewer } = req.body

    if (!image_id || !field_name || !human_value) {
      return res.status(400).json({ error: 'image_id, field_name and human_value are required' })
    }

    // Insert correction record
    await db.query(
      `INSERT INTO corrections (image_id, field_name, ai_value, human_value, reviewer)
       VALUES (?, ?, ?, ?, ?)`,
      [image_id, field_name, ai_value, human_value, reviewer || 'unknown']
    )

    // Mark image as verified in ai_tags
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

// ── POST /api/corrections/confirm — confirm AI tag without changing it ────────
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
