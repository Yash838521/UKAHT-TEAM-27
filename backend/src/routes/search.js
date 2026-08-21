const express = require('express')
const router  = express.Router()
const db      = require('../db')
const http    = require('http')

const SEARCH_PORT = process.env.SEARCH_PORT || 5001

function runClipSearch(query) {
  return new Promise((resolve, reject) => {
    const url = `http://localhost:${SEARCH_PORT}/?q=${encodeURIComponent(query)}`
    http.get(url, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try { resolve(JSON.parse(data)) }
        catch (e) { reject(new Error(`Failed to parse search response: ${data}`)) }
      })
    }).on('error', (err) => {
      reject(new Error(`Search server unavailable — run: python -m ukaht.api.search_server (${err.message})`))
    })
  })
}

// GET /api/search?q=red+tent&scene_type=exterior&quality_min=0.5
router.get('/', async (req, res) => {
  try {
    const { q, scene_type, people_min, quality_min } = req.query

    if (!q) return res.status(400).json({ error: 'Query parameter q is required' })

    // Step 1 — call persistent search server
    // Returns all results above threshold — no fixed limit
    const searchResults = await runClipSearch(q)

    if (!searchResults.length) {
      return res.json({ total: 0, images: [], query: q })
    }

    // Step 2 — map image_uid → similarity score
    const scoreMap = Object.fromEntries(
      searchResults.map(r => [r.image_uid, r.similarity_score])
    )
    const uids = searchResults.map(r => r.image_uid)

    // Step 3 — look up full image details from DB using image_uid
    const conditions = [`i.image_uid IN (${uids.map(() => '?').join(',')})`]
    const params     = [...uids]

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

    const [rows] = await db.query(`
      SELECT
        i.id, i.image_uid, i.filename, i.storage_url, i.uploaded_at,
        e.date_taken, e.camera_make, e.camera_model,
        COALESCE(c_scene.human_value,  a.scene_type)   AS scene_type,
        COALESCE(c_people.human_value, a.people_count) AS people_count,
        a.tags, a.categories, a.caption, a.is_verified,
        q.overall_score, q.is_best_in_group,
        dc.cluster_id, dc.is_representative
      FROM images i
      LEFT JOIN exif_metadata      e        ON e.image_id   = i.id
      LEFT JOIN ai_tags            a        ON a.image_id   = i.id
      LEFT JOIN quality_scores     q        ON q.image_id   = i.id
      LEFT JOIN duplicate_clusters dc       ON dc.image_id  = i.id
      LEFT JOIN corrections        c_scene  ON c_scene.image_id  = i.id AND c_scene.field_name  = 'scene_type'
      LEFT JOIN corrections        c_people ON c_people.image_id = i.id AND c_people.field_name = 'people_count'
      WHERE ${conditions.join(' AND ')}
    `, params)

    // Step 4 — attach similarity score and sort by relevance
    const images = rows
      .map(row => ({ ...row, similarity_score: scoreMap[row.image_uid] || 0 }))
      .sort((a, b) => b.similarity_score - a.similarity_score)

    res.json({ total: images.length, images, query: q })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router