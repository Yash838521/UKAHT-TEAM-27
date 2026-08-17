const express = require('express')
const router  = express.Router()
const db      = require('../db')

// ── GET /api/clusters — all duplicate clusters with member images ──────────────
router.get('/', async (req, res) => {
  try {
    const { page = 1, limit = 10 } = req.query
    const offset = (Number(page) - 1) * Number(limit)

    const [clusters] = await db.query(`
      SELECT
        cluster_id,
        COUNT(*)                                              AS member_count,
        MAX(CASE WHEN is_representative THEN image_id END)   AS representative_id
      FROM duplicate_clusters
      WHERE cluster_id IS NOT NULL
      GROUP BY cluster_id
      ORDER BY member_count DESC
      LIMIT ? OFFSET ?
    `, [Number(limit), offset])

    const enriched = await Promise.all(clusters.map(async cluster => {
      const [members] = await db.query(`
        SELECT
          i.id, i.filename, i.storage_url,
          a.scene_type, a.people_count, a.tags,
          q.overall_score, q.sharpness_score, q.exposure_score,
          dc.similarity_score, dc.is_representative
        FROM duplicate_clusters dc
        JOIN images         i ON i.id = dc.image_id
        LEFT JOIN ai_tags   a ON a.image_id = dc.image_id
        LEFT JOIN quality_scores q ON q.image_id = dc.image_id
        WHERE dc.cluster_id = ?
        ORDER BY q.overall_score DESC
      `, [cluster.cluster_id])

      return { ...cluster, members }
    }))

    const [[{ total }]] = await db.query(
      `SELECT COUNT(DISTINCT cluster_id) AS total FROM duplicate_clusters WHERE cluster_id IS NOT NULL`
    )

    res.json({ total, page: Number(page), clusters: enriched })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── PATCH /api/clusters/:clusterId/representative — override best image ────────
router.patch('/:clusterId/representative', async (req, res) => {
  try {
    const { image_id } = req.body
    const { clusterId } = req.params

    if (!image_id) return res.status(400).json({ error: 'image_id is required' })

    await db.query(
      `UPDATE duplicate_clusters SET is_representative = FALSE WHERE cluster_id = ?`,
      [clusterId]
    )

    await db.query(
      `UPDATE duplicate_clusters SET is_representative = TRUE WHERE cluster_id = ? AND image_id = ?`,
      [clusterId, image_id]
    )

    await db.query(`
      UPDATE quality_scores SET is_best_in_group = FALSE
      WHERE image_id IN (
        SELECT image_id FROM duplicate_clusters WHERE cluster_id = ?
      )
    `, [clusterId])

    await db.query(
      `UPDATE quality_scores SET is_best_in_group = TRUE WHERE image_id = ?`,
      [image_id]
    )

    res.json({ message: 'Representative image updated' })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── DELETE /api/clusters/:clusterId/image/:imageId ────────────────────────────
// Removes one image from a cluster and handles representative reassignment
router.delete('/:clusterId/image/:imageId', async (req, res) => {
  try {
    const clusterId = Number(req.params.clusterId)
    const imageId   = Number(req.params.imageId)
    const wasRep    = req.query.was_representative === 'true'

    // Get remaining members before removal sorted by quality
    const [members] = await db.query(`
      SELECT dc.image_id, dc.is_representative, q.overall_score
      FROM duplicate_clusters dc
      LEFT JOIN quality_scores q ON q.image_id = dc.image_id
      WHERE dc.cluster_id = ? AND dc.image_id != ?
      ORDER BY q.overall_score DESC
    `, [clusterId, imageId])

    // Remove image from cluster
    await db.query(`
      UPDATE duplicate_clusters
      SET cluster_id = NULL, is_representative = FALSE, similarity_score = NULL
      WHERE cluster_id = ? AND image_id = ?
    `, [clusterId, imageId])

    // Reset its quality flag
    await db.query(
      `UPDATE quality_scores SET is_best_in_group = FALSE WHERE image_id = ?`,
      [imageId]
    )

    if (members.length === 1) {
      // Only one image left — dissolve cluster entirely
      await db.query(`
        UPDATE duplicate_clusters
        SET cluster_id = NULL, is_representative = FALSE, similarity_score = NULL
        WHERE cluster_id = ?
      `, [clusterId])

      await db.query(
        `UPDATE quality_scores SET is_best_in_group = TRUE WHERE image_id = ?`,
        [members[0].image_id]
      )

      return res.json({
        message:   'Cluster dissolved — only one image remained',
        dissolved: true
      })
    }

    // Multiple images remain — reassign representative if needed
    if (wasRep) {
      const newRep = members[0] // highest overall_score

      await db.query(
        `UPDATE duplicate_clusters SET is_representative = FALSE WHERE cluster_id = ?`,
        [clusterId]
      )

      await db.query(`
        UPDATE duplicate_clusters
        SET is_representative = TRUE
        WHERE cluster_id = ? AND image_id = ?
      `, [clusterId, newRep.image_id])

      await db.query(`
        UPDATE quality_scores SET is_best_in_group = FALSE
        WHERE image_id IN (
          SELECT image_id FROM duplicate_clusters WHERE cluster_id = ?
        )
      `, [clusterId])

      await db.query(
        `UPDATE quality_scores SET is_best_in_group = TRUE WHERE image_id = ?`,
        [newRep.image_id]
      )

      return res.json({
        message:            'Image removed, new representative assigned',
        new_representative: newRep.image_id,
        dissolved:          false
      })
    }

    res.json({ message: 'Image removed from cluster', dissolved: false })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── DELETE /api/clusters/:clusterId — dissolve entire cluster ─────────────────
router.delete('/:clusterId', async (req, res) => {
  try {
    const clusterId = Number(req.params.clusterId)

    // Get all members to reset quality flags
    const [members] = await db.query(
      `SELECT image_id FROM duplicate_clusters WHERE cluster_id = ?`,
      [clusterId]
    )

    // Remove all from cluster
    await db.query(`
      UPDATE duplicate_clusters
      SET cluster_id = NULL, is_representative = FALSE, similarity_score = NULL
      WHERE cluster_id = ?
    `, [clusterId])

    // All images become their own best
    for (const { image_id } of members) {
      await db.query(
        `UPDATE quality_scores SET is_best_in_group = TRUE WHERE image_id = ?`,
        [image_id]
      )
    }

    res.json({ message: 'Cluster dissolved', count: members.length })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router