const express = require('express')
const router  = express.Router()
const db      = require('../db')
const { spawn } = require('child_process')
const path    = require('path')

const PYTHON     = process.env.PYTHON_PATH || 'python'
const SEARCH_PY  = path.join(__dirname, '../scripts/clip_search.py')

// ── Helper: call Python CLIP search script ───────────────────────────────────
function runClipSearch(query, model) {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON, [SEARCH_PY, '--query', query, '--model', model])

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', d => stdout += d)
    proc.stderr.on('data', d => stderr += d)

    proc.on('close', code => {
      if (code !== 0) return reject(new Error(`CLIP search failed: ${stderr}`))
      try {
        resolve(JSON.parse(stdout))
      } catch (e) {
        reject(new Error(`Failed to parse CLIP search output: ${stdout}`))
      }
    })
  })
}

// ── GET /api/search ──────────────────────────────────────────────────────────
// Query params:
//   q           — search text (required)
//   model       — clip model name (default: clip-vit-base-patch32)
//   scene_type  — optional filter stacked on top of search results
//   people_min  — optional filter
//   quality_min — optional filter
//   limit       — max results to return (default: 50)
router.get('/', async (req, res) => {
  try {
    const {
      q,
      model       = 'clip-vit-base-patch32',
      scene_type,
      people_min,
      quality_min,
      limit       = 50
    } = req.query

    if (!q) return res.status(400).json({ error: 'Query parameter q is required' })

    // Step 1 — run CLIP search, get ranked image IDs with similarity scores
    const searchResults = await runClipSearch(q, model)
    // searchResults = [{ image_id: 47, similarity: 0.38 }, ...]

    if (!searchResults.length) {
      return res.json({ results: [], message: 'No relevant images found' })
    }

    const imageIds    = searchResults.map(r => r.image_id)
    const scoreMap    = Object.fromEntries(searchResults.map(r => [r.image_id, r.similarity]))

    // Step 2 — fetch full image data for ranked IDs, apply any additional filters
    const conditions = [`i.id IN (${imageIds.map(() => '?').join(',')})`]
    const params     = [...imageIds]

    if (scene_type) {
      conditions.push(`COALESCE(c_scene.human_value, a.scene_type) = ?`)
      params.push(scene_type)
    }
    if (people_min !== undefined) {
      conditions.push(`COALESCE(c_people.human_value, a.people_count) >= ?`)
      params.push(Number(people_min))
    }
    if (quality_min !== undefined) {
      conditions.push(`q.overall_score >= ?`)
      params.push(Number(quality_min))
    }

    const where = `WHERE ${conditions.join(' AND ')}`

    const [rows] = await db.query(`
      SELECT
        i.id, i.filename, i.storage_url,
        e.date_taken, e.camera_make, e.camera_model,
        COALESCE(c_scene.human_value,  a.scene_type)   AS scene_type,
        COALESCE(c_people.human_value, a.people_count) AS people_count,
        a.tags, a.categories, a.is_verified,
        q.overall_score, q.is_best_in_group,
        dc.cluster_id, dc.is_representative
      FROM images i
      LEFT JOIN exif_metadata      e        ON e.image_id   = i.id
      LEFT JOIN ai_tags            a        ON a.image_id   = i.id
      LEFT JOIN quality_scores     q        ON q.image_id   = i.id
      LEFT JOIN duplicate_clusters dc       ON dc.image_id  = i.id
      LEFT JOIN corrections        c_scene  ON c_scene.image_id  = i.id AND c_scene.field_name  = 'scene_type'
      LEFT JOIN corrections        c_people ON c_people.image_id = i.id AND c_people.field_name = 'people_count'
      ${where}
    `, params)

    // Step 3 — attach similarity score and sort by relevance
    const withScores = rows
      .map(row => ({ ...row, similarity: scoreMap[row.id] || 0 }))
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, Number(limit))

    res.json({
      results: withScores,
      query:   q,
      model:   model,
      message: null
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
