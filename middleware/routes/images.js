const express = require('express')
const router  = express.Router()
const db      = require('../db')

// ── Helper: build the base SELECT with all joined tables ─────────────────────
function baseSelect() {
  return `
    SELECT
      i.id,
      i.filename,
      i.storage_url,
      i.uploaded_at,
      i.processed,
      e.date_taken,
      e.camera_make,
      e.camera_model,
      e.image_width,
      e.image_height,
      e.iso,
      e.flash,
      e.gps_latitude,
      e.gps_longitude,
      COALESCE(c_scene.human_value,   a.scene_type)    AS scene_type,
      COALESCE(c_people.human_value,  a.people_count)  AS people_count,
      a.scene_confidence,
      a.people_confidence,
      a.tags,
      a.categories,
      a.model_name,
      a.is_verified,
      q.sharpness_score,
      q.exposure_score,
      q.overall_score,
      q.is_best_in_group,
      dc.cluster_id,
      dc.is_representative,
      dc.similarity_score
    FROM images i
    LEFT JOIN exif_metadata      e        ON e.image_id   = i.id
    LEFT JOIN ai_tags            a        ON a.image_id   = i.id
    LEFT JOIN quality_scores     q        ON q.image_id   = i.id
    LEFT JOIN duplicate_clusters dc       ON dc.image_id  = i.id
    LEFT JOIN corrections        c_scene  ON c_scene.image_id  = i.id AND c_scene.field_name  = 'scene_type'
    LEFT JOIN corrections        c_people ON c_people.image_id = i.id AND c_people.field_name = 'people_count'
  `
}

// ── GET /api/images — browse with filters ────────────────────────────────────
router.get('/', async (req, res) => {
  try {
    const {
      scene_type,
      people_min,
      people_max,
      date_from,
      date_to,
      quality_min,
      best_only,
      no_duplicates,
      tag,
      category,
      sort    = 'overall_score',
      order   = 'DESC',
      page    = 1,
      limit   = 24
    } = req.query

    const conditions = []
    const params     = []

    if (scene_type) {
      conditions.push(`COALESCE(c_scene.human_value, a.scene_type) = ?`)
      params.push(scene_type)
    }

    if (people_min !== undefined) {
      conditions.push(`COALESCE(c_people.human_value, a.people_count) >= ?`)
      params.push(Number(people_min))
    }

    if (people_max !== undefined) {
      conditions.push(`COALESCE(c_people.human_value, a.people_count) <= ?`)
      params.push(Number(people_max))
    }

    if (date_from) {
      conditions.push(`e.date_taken >= ?`)
      params.push(date_from)
    }

    if (date_to) {
      conditions.push(`e.date_taken <= ?`)
      params.push(date_to)
    }

    if (quality_min !== undefined) {
      conditions.push(`q.overall_score >= ?`)
      params.push(Number(quality_min))
    }

    if (best_only === 'true') {
      conditions.push(`q.is_best_in_group = TRUE`)
    }

    if (no_duplicates === 'true') {
      conditions.push(`(dc.cluster_id IS NULL OR dc.is_representative = TRUE)`)
    }

    if (tag) {
      conditions.push(`JSON_CONTAINS(a.tags, JSON_OBJECT('tag', ?))`)
      params.push(tag)
    }

    if (category) {
      conditions.push(`JSON_CONTAINS(a.categories, JSON_OBJECT('category', ?))`)
      params.push(category)
    }

    const where  = conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''
    const offset = (Number(page) - 1) * Number(limit)

    // Validate sort column to prevent SQL injection
    const allowedSort = ['overall_score', 'date_taken', 'people_count', 'filename']
    const safeSort    = allowedSort.includes(sort) ? sort : 'overall_score'
    const safeOrder   = order === 'ASC' ? 'ASC' : 'DESC'

    const sql = `
      ${baseSelect()}
      ${where}
      ORDER BY ${safeSort} ${safeOrder}
      LIMIT ? OFFSET ?
    `

    const countSql = `
      SELECT COUNT(*) AS total
      FROM images i
      LEFT JOIN exif_metadata      e        ON e.image_id   = i.id
      LEFT JOIN ai_tags            a        ON a.image_id   = i.id
      LEFT JOIN quality_scores     q        ON q.image_id   = i.id
      LEFT JOIN duplicate_clusters dc       ON dc.image_id  = i.id
      LEFT JOIN corrections        c_scene  ON c_scene.image_id  = i.id AND c_scene.field_name  = 'scene_type'
      LEFT JOIN corrections        c_people ON c_people.image_id = i.id AND c_people.field_name = 'people_count'
      ${where}
    `

    const [rows]    = await db.query(sql,      [...params, Number(limit), offset])
    const [countRow] = await db.query(countSql, params)

    res.json({
      total:  countRow[0].total,
      page:   Number(page),
      limit:  Number(limit),
      pages:  Math.ceil(countRow[0].total / Number(limit)),
      images: rows
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── GET /api/images/recent — recently uploaded images ────────────────────────
router.get('/recent', async (req, res) => {
  try {
    const { limit = 10 } = req.query
    const [rows] = await db.query(`
      ${baseSelect()}
      ORDER BY i.uploaded_at DESC
      LIMIT ?
    `, [Number(limit)])
    res.json(rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── GET /api/images/:id — single image detail ────────────────────────────────
router.get('/:id', async (req, res) => {
  try {
    const [rows] = await db.query(`
      ${baseSelect()}
      WHERE i.id = ?
    `, [req.params.id])

    if (!rows.length) return res.status(404).json({ error: 'Image not found' })
    res.json(rows[0])
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── GET /api/images/:id/similar — images in the same duplicate cluster ───────
router.get('/:id/similar', async (req, res) => {
  try {
    // Get cluster_id of this image
    const [[image]] = await db.query(
      `SELECT cluster_id FROM duplicate_clusters WHERE image_id = ?`,
      [req.params.id]
    )

    if (!image || !image.cluster_id) return res.json([])

    const [rows] = await db.query(`
      ${baseSelect()}
      WHERE dc.cluster_id = ? AND i.id != ?
      ORDER BY q.overall_score DESC
    `, [image.cluster_id, req.params.id])

    res.json(rows)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
