const express    = require('express')
const router     = express.Router()
const db         = require('../db')
const { spawn }  = require('child_process')
const path       = require('path')

const PYTHON      = process.env.PYTHON_PATH || 'python'
const PIPELINE_PY = path.join(__dirname, '../../db/scripts/load_exif_metadata.py')

// ── GET /api/pipeline/status — how many images are processed vs pending ───────
router.get('/status', async (req, res) => {
  try {
    const [[counts]] = await db.query(`
      SELECT
        COUNT(*)                                             AS total,
        SUM(CASE WHEN processed = TRUE  THEN 1 ELSE 0 END) AS processed,
        SUM(CASE WHEN processed = FALSE THEN 1 ELSE 0 END) AS pending
      FROM images
    `)

    const [[tagged]] = await db.query(`
      SELECT COUNT(*) AS count FROM ai_tags WHERE scene_type IS NOT NULL
    `)

    const [[scored]] = await db.query(`
      SELECT COUNT(*) AS count FROM quality_scores WHERE overall_score IS NOT NULL
    `)

    const [[embedded]] = await db.query(`
      SELECT COUNT(*) AS count FROM embeddings WHERE vector_json IS NOT NULL
    `)

    res.json({
      total_images:    counts.total,
      processed:       counts.processed,
      pending:         counts.pending,
      ai_tagged:       tagged.count,
      quality_scored:  scored.count,
      embedded:        embedded.count
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── POST /api/pipeline/run — trigger pipeline for unprocessed images ──────────
// Note: this triggers the Python pipeline as a background subprocess
// The response returns immediately — progress can be checked via GET /status
router.post('/run', (req, res) => {
  try {
    const proc = spawn(PYTHON, [PIPELINE_PY], {
      detached: true,
      stdio:    'ignore'
    })
    proc.unref()  // allow Node to exit even if Python is still running

    res.json({
      message: 'Pipeline started — check /api/pipeline/status for progress'
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
