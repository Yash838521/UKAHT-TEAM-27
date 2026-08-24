const express  = require('express')
const router   = express.Router()
const db       = require('../db')
const multer   = require('multer')
const path     = require('path')
const fs       = require('fs')
const crypto   = require('crypto')

const STORAGE_TYPE = process.env.STORAGE_TYPE    || 'local'
const PIPELINE_DIR = process.env.PIPELINE_DIR    || path.join(__dirname, '../../../pipeline')
const PYTHON       = process.env.PYTHON_PATH     || 'python3'
const SQS_QUEUE    = process.env.SQS_QUEUE_URL   || ''
const AWS_REGION   = process.env.AWS_REGION      || 'eu-west-2'
const S3_BUCKET    = process.env.AWS_BUCKET_NAME || ''

function generateImageUid() {
  return crypto.randomBytes(16).toString('hex')
}

// AWS mode — notify pipeline worker via SQS
async function notifyPipeline(imageUid, imagePath) {
  if (!SQS_QUEUE) return
  try {
    const { SQSClient, SendMessageCommand } = require('@aws-sdk/client-sqs')
    const sqs = new SQSClient({ region: AWS_REGION })
    await sqs.send(new SendMessageCommand({
      QueueUrl:    SQS_QUEUE,
      MessageBody: JSON.stringify({ image_uid: imageUid, image_path: imagePath })
    }))
    console.log(`SQS message sent for ${imageUid}`)
  } catch (err) {
    console.error(`SQS notify failed: ${err.message}`)
  }
}

// Local mode — encode CLIP embedding directly
function encodeLocal(imagePath, imageUid) {
  const { spawn } = require('child_process')
  const proc = spawn(PYTHON, [
    '-m', 'ukaht.ingest.encode_single',
    '--image-path', imagePath,
    '--image-uid',  imageUid
  ], {
    cwd:      PIPELINE_DIR,
    env:      { ...process.env, PYTHONPATH: 'src', KMP_DUPLICATE_LIB_OK: 'TRUE' },
    detached: true,
    stdio:    'ignore'
  })
  proc.unref()
}

// Accept file via multer regardless of mode — in S3 mode we use it temporarily then delete
const localStorage = multer.diskStorage({
  destination: (req, file, cb) => {
    const uploadDir = path.join(process.env.LOCAL_IMAGE_BASE || '/tmp', 'uploads')
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
    allowed.includes(ext) ? cb(null, true) : cb(new Error('Only image files are allowed'))
  }
})

router.post('/batch/start', async (req, res) => {
  try {
    const { uploaded_by = 'staff', total_files = 0 } = req.body
    const [result] = await db.query(
      `INSERT INTO upload_batches (uploaded_by, total_files, success, failed) VALUES (?, ?, 0, 0)`,
      [uploaded_by, total_files]
    )
    res.status(201).json({ batch_id: result.insertId, uploaded_by, total_files, message: 'Batch started' })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

router.patch('/batch/:id', async (req, res) => {
  try {
    const { success = 0, failed = 0 } = req.body
    await db.query(
      `UPDATE upload_batches SET success = ?, failed = ? WHERE id = ?`,
      [success, failed, Number(req.params.id)]
    )
    res.json({ message: 'Batch updated', batch_id: Number(req.params.id), success, failed })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

router.get('/batches', async (req, res) => {
  try {
    const [batches] = await db.query(`
      SELECT id, uploaded_by, uploaded_at, total_files, success, failed
      FROM upload_batches ORDER BY uploaded_at DESC
    `)
    res.json(batches)
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

router.get('/batches/:id', async (req, res) => {
  try {
    const [batch] = await db.query(`SELECT * FROM upload_batches WHERE id = ?`, [Number(req.params.id)])
    if (!batch.length) return res.status(404).json({ error: 'Batch not found' })
    const [images] = await db.query(
      `SELECT id, filename, storage_url, uploaded_at, processed FROM images WHERE batch_id = ? ORDER BY uploaded_at ASC`,
      [Number(req.params.id)]
    )
    res.json({ batch: batch[0], images })
  } catch (err) {
    console.error(err)
    res.status(500).json({ error: err.message })
  }
})

// Main upload endpoint — handles both local and S3 modes
router.post('/', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file uploaded' })

    const batchId  = req.body.batch_id ? Number(req.body.batch_id) : null
    const imageUid = generateImageUid()

    // AWS S3 mode — generate presigned URL and return to Angular
    // Angular will PUT directly to S3 then call /confirm-s3
    if (STORAGE_TYPE === 's3') {
      const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3')
      const { getSignedUrl }               = require('@aws-sdk/s3-request-presigner')
      const s3  = new S3Client({ region: AWS_REGION })
      const key = `uploads/${Date.now()}-${req.file.originalname}`

      const command = new PutObjectCommand({
        Bucket:      S3_BUCKET,
        Key:         key,
        ContentType: req.file.mimetype
      })
      const signedUrl   = await getSignedUrl(s3, command, { expiresIn: 300 })
      const storage_url = `s3://${S3_BUCKET}/${key}`

      // Delete the temp file — we don't need it in S3 mode
      try { fs.unlinkSync(req.file.path) } catch {}

      return res.json({
        mode:        's3',
        upload_url:  signedUrl,
        storage_url: storage_url,
        image_uid:   imageUid,
        batch_id:    batchId,
        filename:    req.file.originalname
      })
    }

    // Local mode — file saved to disk, encode CLIP directly
    const storageUrl = req.file.path.replace(/\\/g, '/')
    const [result]   = await db.query(
      `INSERT INTO images (image_uid, filename, storage_url, processed, batch_id) VALUES (?, ?, ?, FALSE, ?)`,
      [imageUid, req.file.originalname, storageUrl, batchId]
    )
    const imageId = result.insertId
    await db.query(`INSERT INTO embeddings (image_id, image_uid) VALUES (?, ?)`, [imageId, imageUid])
    encodeLocal(storageUrl, imageUid)

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

// Called by Angular after successful S3 upload — registers image in DB and triggers pipeline
router.post('/confirm-s3', async (req, res) => {
  try {
    const { filename, storage_url, batch_id, image_uid } = req.body
    if (!filename || !storage_url) {
      return res.status(400).json({ error: 'filename and storage_url are required' })
    }

    const batchId  = batch_id  ? Number(batch_id) : null
    const imageUid = image_uid || generateImageUid()

    const [result] = await db.query(
      `INSERT INTO images (image_uid, filename, storage_url, processed, batch_id) VALUES (?, ?, ?, FALSE, ?)`,
      [imageUid, filename, storage_url, batchId]
    )
    const imageId = result.insertId
    await db.query(`INSERT INTO embeddings (image_id, image_uid) VALUES (?, ?)`, [imageId, imageUid])

    await notifyPipeline(imageUid, storage_url)

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