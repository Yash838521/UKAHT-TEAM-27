const express  = require('express')
const router   = express.Router()
const db       = require('../db')
const multer   = require('multer')
const path     = require('path')
const fs       = require('fs')
const crypto   = require('crypto')
const { spawn } = require('child_process')

const STORAGE_TYPE  = process.env.STORAGE_TYPE  || 'local'
const PIPELINE_DIR  = process.env.PIPELINE_DIR  || path.join(__dirname, '../../../pipeline')
const PYTHON        = process.env.PYTHON_PATH   || 'python'

// Generate image_uid — same method as pipeline (md5 hex of filename+timestamp) ──
function generateImageUid() {
  return crypto.randomBytes(16).toString('hex')
}

// Spawn CLIP encode for new image
function encodeImage(imagePath, imageUid) {
  const proc = spawn(PYTHON, [
    '-m', 'ukaht.ingest.encode_single',
    '--image-path', imagePath,
    '--image-uid',  imageUid
  ], {
    cwd: PIPELINE_DIR,
    env: {
      ...process.env,
      PYTHONPATH:            'src',
      KMP_DUPLICATE_LIB_OK:  'TRUE',
    },
    detached: true,
    stdio:    'ignore'
  })
  proc.unref() 
}

// Local storage setup (dev)
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
  limits: { fileSize: 20 * 1024 * 1024 },
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

// POST /api/upload/batch/start
router.post('/batch/start', async (req, res) => {
  try {
    const { uploaded_by = 'staff', total_files = 0 } = req.body

    const [result] = await db.query(
      `INSERT INTO upload_batches (uploaded_by, total_files, success, failed)
       VALUES (?, ?, 0, 0)`,
      [uploaded_by, total_files]
    )

    res.status(201).json({
      batch_id:    result.insertId,
      uploaded_by,
      total_files,
      message:     'Batch started'
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/upload/batch/:id
router.patch('/batch/:id', async (req, res) => {
  try {
    const batchId              = Number(req.params.id)
    const { success = 0, failed = 0 } = req.body

    await db.query(
      `UPDATE upload_batches SET success = ?, failed = ? WHERE id = ?`,
      [success, failed, batchId]
    )

    res.json({ message: 'Batch updated', batch_id: batchId, success, failed })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/upload/
router.get('/batches', async (req, res) => {
  try {
    const [batches] = await db.query(`
      SELECT id, uploaded_by, uploaded_at, total_files, success, failed
      FROM upload_batches
      ORDER BY uploaded_at DESC
    `)
    res.json(batches)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/upload/batches/:id
router.get('/batches/:id', async (req, res) => {
  try {
    const batchId = Number(req.params.id)

    const [batch] = await db.query(
      `SELECT * FROM upload_batches WHERE id = ?`,
      [batchId]
    )

    if (!batch.length) return res.status(404).json({ error: 'Batch not found' })

    const [images] = await db.query(
      `SELECT id, filename, storage_url, uploaded_at, processed
       FROM images WHERE batch_id = ? ORDER BY uploaded_at ASC`,
      [batchId]
    )

    res.json({ batch: batch[0], images })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/upload/presigned-url
router.get('/presigned-url', async (req, res) => {
  if (STORAGE_TYPE !== 's3') {
    return res.status(400).json({ error: 'Pre-signed URLs only available in S3 mode' })
  }

  try {
    const { filename, contentType } = req.query
    if (!filename) return res.status(400).json({ error: 'filename is required' })

    const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3')
    const { getSignedUrl }               = require('@aws-sdk/s3-request-presigner')

    const s3  = new S3Client({ region: process.env.AWS_REGION })
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

// POST /api/upload
router.post('/', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' })

    const batchId    = req.body.batch_id ? Number(req.body.batch_id) : null
    const imageUid   = generateImageUid()
    const storageUrl = STORAGE_TYPE === 's3'
      ? req.body.storage_url
      : req.file.path.replace(/\\/g, '/')

    const [result] = await db.query(
      `INSERT INTO images (image_uid, filename, storage_url, processed, batch_id)
       VALUES (?, ?, ?, FALSE, ?)`,
      [imageUid, req.file.originalname, storageUrl, batchId]
    )

    const imageId = result.insertId

    await db.query(`INSERT INTO ai_tags (image_id) VALUES (?)`,            [imageId])
    await db.query(`INSERT INTO quality_scores (image_id) VALUES (?)`,     [imageId])
    await db.query(`INSERT INTO duplicate_clusters (image_id) VALUES (?)`, [imageId])
    await db.query(`INSERT INTO embeddings (image_id, image_uid) VALUES (?, ?)`, [imageId, imageUid])

    // Encode image with CLIP in background — non-blocking
    encodeImage(storageUrl, imageUid)

    res.status(201).json({
      message:     'Image uploaded successfully',
      image_id:    imageId,
      image_uid:   imageUid,
      filename:    req.file.originalname,
      storage_url: storageUrl,
      batch_id:    batchId
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// POST /api/upload/confirm-s3
router.post('/confirm-s3', async (req, res) => {
  try {
    const { filename, storage_url, batch_id } = req.body
    if (!filename || !storage_url) {
      return res.status(400).json({ error: 'filename and storage_url are required' })
    }

    const batchId  = batch_id ? Number(batch_id) : null
    const imageUid = generateImageUid()

    const [result] = await db.query(
      `INSERT INTO images (image_uid, filename, storage_url, processed, batch_id)
       VALUES (?, ?, ?, FALSE, ?)`,
      [imageUid, filename, storage_url, batchId]
    )

    const imageId = result.insertId

    await db.query(`INSERT INTO ai_tags (image_id) VALUES (?)`,            [imageId])
    await db.query(`INSERT INTO quality_scores (image_id) VALUES (?)`,     [imageId])
    await db.query(`INSERT INTO duplicate_clusters (image_id) VALUES (?)`, [imageId])
    await db.query(`INSERT INTO embeddings (image_id, image_uid) VALUES (?, ?)`, [imageId, imageUid])

    // Encode image with CLIP in background — non-blocking
    // For S3, storage_url is the S3 path — encode_single handles both local and S3
    encodeImage(storage_url, imageUid)

    res.status(201).json({
      message:   'Image registered successfully',
      image_id:  imageId,
      image_uid: imageUid,
      batch_id:  batchId
    })

  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

module.exports = router