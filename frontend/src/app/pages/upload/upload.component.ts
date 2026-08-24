import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { HttpClient } from '@angular/common/http'
import { UploadService } from '../../services/upload.service'
import { environment } from '../../../../environments/environment'

interface UploadFile {
  file:     File
  status:   'pending' | 'uploading' | 'success' | 'error'
  progress: number
  error?:   string
}

@Component({
  selector:    'app-upload',
  templateUrl: './upload.component.html',
  styleUrls:   ['./upload.component.scss'],
  standalone:  true,
  imports:     [CommonModule, FormsModule, RouterModule]
})
export class UploadComponent implements OnInit {
  files:          UploadFile[] = []
  isDragging:     boolean      = false
  uploading:      boolean      = false
  batchId:        number | null = null
  uploadedCount:  number       = 0
  failedCount:    number       = 0
  runPipeline:    boolean      = true
  overwrite:      boolean      = false
  batches:        any[]        = []

  constructor(
    private uploadService: UploadService,
    private http:          HttpClient
  ) {}

  ngOnInit() {
    this.loadBatches()
  }

  loadBatches() {
    this.uploadService.getBatches().subscribe({
      next:  batches => this.batches = batches,
      error: ()      => {}
    })
  }

  onDragOver(event: DragEvent) {
    event.preventDefault()
    this.isDragging = true
  }

  onDragLeave(event: DragEvent) {
    this.isDragging = false
  }

  onDrop(event: DragEvent) {
    event.preventDefault()
    this.isDragging = false
    const files = Array.from(event.dataTransfer?.files || [])
    this.addFiles(files)
  }

  onFileSelect(event: Event) {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files || [])
    this.addFiles(files)
    input.value = ''
  }

  addFiles(files: File[]) {
    const allowed = ['.jpg', '.jpeg', '.png', '.tiff']
    for (const file of files) {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!allowed.includes(ext)) continue
      if (file.size > 20 * 1024 * 1024) continue
      this.files.push({ file, status: 'pending', progress: 0 })
    }
  }

  removeFile(index: number) {
    this.files.splice(index, 1)
  }

  clearAll() {
    this.files = this.files.filter(f => f.status === 'uploading')
  }

  async startUpload() {
    if (!this.files.length || this.uploading) return

    this.uploading     = true
    this.uploadedCount = 0
    this.failedCount   = 0

    // Start batch
    const pending = this.files.filter(f => f.status === 'pending')
    try {
      const batch   = await this.uploadService.startBatch('staff', pending.length).toPromise()
      this.batchId  = batch.batch_id
    } catch {
      this.batchId = null
    }

    // Upload files sequentially
    for (const uploadFile of pending) {
      await this.uploadSingleFile(uploadFile)
    }

    // Update batch counts
    if (this.batchId) {
      this.uploadService.updateBatch(this.batchId, this.uploadedCount, this.failedCount).subscribe()
    }

    this.uploading = false
    this.loadBatches()
  }

  async uploadSingleFile(uploadFile: UploadFile) {
    uploadFile.status   = 'uploading'
    uploadFile.progress = 10

    try {
      const formData = new FormData()
      formData.append('image', uploadFile.file)
      if (this.batchId) formData.append('batch_id', String(this.batchId))

      // Step 1 — POST to /api/upload
      const response: any = await this.http.post(
        `${environment.apiUrl}/upload`,
        formData
      ).toPromise()

      uploadFile.progress = 50

      // Step 2 — if S3 mode, upload directly to S3 then confirm
      if (response.mode === 's3') {
        await fetch(response.upload_url, {
          method:  'PUT',
          body:    uploadFile.file,
          headers: { 'Content-Type': uploadFile.file.type }
        })

        uploadFile.progress = 80

        await this.http.post(`${environment.apiUrl}/upload/confirm-s3`, {
          filename:    response.filename,
          storage_url: response.storage_url,
          batch_id:    response.batch_id,
          image_uid:   response.image_uid
        }).toPromise()
      }

      uploadFile.status   = 'success'
      uploadFile.progress = 100
      this.uploadedCount++

    } catch (err: any) {
      uploadFile.status = 'error'
      uploadFile.error  = err?.message || 'Upload failed'
      this.failedCount++
    }
  }

  get pendingCount()  { return this.files.filter(f => f.status === 'pending').length }
  get successCount()  { return this.files.filter(f => f.status === 'success').length }
  get errorCount()    { return this.files.filter(f => f.status === 'error').length }
  get hasFiles()      { return this.files.length > 0 }
  get allDone()       { return this.files.every(f => f.status === 'success' || f.status === 'error') }
}