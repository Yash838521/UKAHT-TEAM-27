const express  = require('express')
const router   = express.Router()
const db       = require('../db')
const multer   = require('multer')
const path     = require('path')
const fs       = require('fs')

const STORAGE_TYPE = process.env.STORAGE_TYPE || 'local'

// ── Local storage setup (dev) ─────────────────────────────────────────────────
const localStorage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(process.env.LOCAL_IMAGE_BASE || './uploads', 'uploads')
    fs.mkdirSync(uploadDir, { recursive: true })
    cb(null, uploadDir)
  },
  filename: (req, file, cb) => {
    cb(null, `${Date.now()}-${file.originalname}`)
  }
})

const upload = multer({
  storage: localStorage,
  fileFilter: (req, file, cb) => {
    const allowed = ['.jpg', '.jpeg', '.png', '.tiff']
    const ext     = path.extname(file.originalname).toLowerCase()
    if (allowed.includes(ext)) {
      cb(null, true)
    } else {
      cb(new Error('Only image files are allowed'))
    }
  }
})

// ── GET /api/upload/presigned-url — generate S3 pre-signed URL (prod) ────────
router.get('/presigned-url', async (req, res) => {
  if (STORAGE_TYPE !== 's3') {
    return res.status(400).json({ error: 'Pre-signed URLs only available in S3 mode' })
  }

  try {
    const { filename, contentType } = req.query
    if (!filename) return res.status(400).json({ error: 'filename is required' })

    const { S3Client, PutObjectCommand }    = require('@aws-sdk/client-s3')
    const { getSignedUrl }                  = require('@aws-sdk/s3-request-presigner')

    const s3 = new S3Client({ region: process.env.AWS_REGION })
    const key = `uploads/${Date.now()}-${filename}`

    const command   = new PutObjectCommand({
      Bucket:      process.env.AWS_BUCKET_NAME,
      Key:         key,
      ContentType: contentType || 'image/jpeg'
    })

    const signedUrl = await getSignedUrl(s3, command, { expiresIn: 300 })

    res.json({
      upload_url:  signedUrl,
      storage_url: `s3://${process.env.AWS_BUCKET_NAME}/${key}`,
      key
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── POST /api/upload — upload image file (local dev) ─────────────────────────
router.post('/', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' })

    const storageUrl = STORAGE_TYPE === 's3'
      ? req.body.storage_url  // passed from frontend after direct S3 upload
      : req.file.path.replace(/\\/g, '/')

    // Insert into images table — unprocessed until pipeline runs
    const [result] = await db.query(
      `INSERT INTO images (filename, storage_url, processed)
       VALUES (?, ?, FALSE)`,
      [req.file.originalname, storageUrl]
    )

    const imageId = result.insertId

    // Create empty placeholder rows in all pipeline tables
    await db.query(`INSERT INTO ai_tags (image_id) VALUES (?)`,           [imageId])
    await db.query(`INSERT INTO quality_scores (image_id) VALUES (?)`,    [imageId])
    await db.query(`INSERT INTO duplicate_clusters (image_id) VALUES (?)`, [imageId])
    await db.query(`INSERT INTO embeddings (image_id) VALUES (?)`,        [imageId])

    res.status(201).json({
      message:     'Image uploaded successfully',
      image_id:    imageId,
      filename:    req.file.originalname,
      storage_url: storageUrl
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// ── POST /api/upload/confirm-s3 — confirm S3 upload and register in DB ───────
router.post('/confirm-s3', async (req, res) => {
  try {
    const { filename, storage_url } = req.body
    if (!filename || !storage_url) {
      return res.status(400).json({ error: 'filename and storage_url are required' })
    }

    const [result] = await db.query(
      `INSERT INTO images (filename, storage_url, processed)
       VALUES (?, ?, FALSE)`,
      [filename, storage_url]
    )

    const imageId = result.insertId
    await db.query(`INSERT INTO ai_tags (image_id) VALUES (?)`,           [imageId])
    await db.query(`INSERT INTO quality_scores (image_id) VALUES (?)`,    [imageId])
    await db.query(`INSERT INTO duplicate_clusters (image_id) VALUES (?)`, [imageId])
    await db.query(`INSERT INTO embeddings (image_id) VALUES (?)`,        [imageId])

    res.status(201).json({
      message:  'Image registered successfully',
      image_id: imageId
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router
