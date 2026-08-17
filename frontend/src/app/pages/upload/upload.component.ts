import { Component, OnInit, ElementRef, ViewChild } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { UploadService } from '../../services/upload.service'
import { QueueFile, UploadBatch, BatchDetail, FileStatus } from '../../models'

@Component({
  selector: 'app-upload',
  templateUrl: './upload.component.html',
  styleUrls: ['./upload.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule]
})
export class UploadComponent implements OnInit {
  @ViewChild('fileInput') fileInputRef!: ElementRef<HTMLInputElement>

  // ── Tab state ─────────────────────────────────────
  activeTab: 'upload' | 'history' = 'upload'

  // ── Upload tab state ──────────────────────────────
  queue:          QueueFile[] = []
  isDragging:     boolean     = false
  isUploading:    boolean     = false
  uploadedBy:     string      = 'staff'

  // Options
  runPipeline:    boolean = true
  skipDuplicates: boolean = true
  overwrite:      boolean = false

  // Progress tracking
  currentBatchId: number | null = null
  successCount:   number        = 0
  failedCount:    number        = 0

  // ── History tab state ─────────────────────────────
  batches:          UploadBatch[]           = []
  batchesLoading:   boolean                 = false
  expandedBatchId:  number | null           = null
  batchDetails:     Record<number, BatchDetail> = {}
  batchDetailLoading: boolean               = false

  constructor(private uploadService: UploadService) {}

  ngOnInit() {
    // Pre-load history when component mounts
    this.loadBatches()
  }

  // ── Tab switching ────────────────────────────────

  setTab(tab: 'upload' | 'history') {
    this.activeTab = tab
    if (tab === 'history') {
      this.loadBatches()
    }
  }

  // ── Drag and drop ────────────────────────────────

  onDragOver(event: DragEvent) {
    event.preventDefault()
    this.isDragging = true
  }

  onDragLeave() {
    this.isDragging = false
  }

  onDrop(event: DragEvent) {
    event.preventDefault()
    this.isDragging = false
    const files = event.dataTransfer?.files
    if (files) {
      this.addFiles(files)
    }
  }

  openFilePicker() {
    this.fileInputRef.nativeElement.click()
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement
    if (input.files) {
      this.addFiles(input.files)
      // Reset so same file can be re-selected
      input.value = ''
    }
  }

  addFiles(files: FileList) {
    const allowed   = ['.jpg', '.jpeg', '.png', '.tiff']
    const maxSizeMB = 20

    Array.from(files).forEach(file => {
      const ext      = '.' + file.name.split('.').pop()?.toLowerCase()
      const sizeMB   = file.size / (1024 * 1024)
      const isDupe   = this.queue.some(q => q.file.name === file.name)

      if (!allowed.includes(ext)) return   // wrong format — skip silently
      if (sizeMB > maxSizeMB) return        // too large — skip silently
      if (isDupe) return                    // already in queue — skip

      this.queue.push({
        file,
        status:   'ready',
        progress: 0,
        error:    ''
      })
    })
  }

  removeFile(index: number) {
    this.queue.splice(index, 1)
  }

  clearQueue() {
    this.queue = this.queue.filter(f => f.status === 'uploading')
  }

  // ── Upload ────────────────────────────────────────

  get readyFiles(): QueueFile[] {
    return this.queue.filter(f => f.status === 'ready' || f.status === 'failed')
  }

  get totalSizeMB(): string {
    const total = this.queue.reduce((sum, f) => sum + f.file.size, 0)
    return (total / (1024 * 1024)).toFixed(1)
  }

  get canUpload(): boolean {
    return this.readyFiles.length > 0 && !this.isUploading
  }

  get uploadBtnLabel(): string {
    if (this.isUploading) return 'Uploading…'
    const failed = this.queue.filter(f => f.status === 'failed').length
    if (failed > 0) return `↺ Retry ${failed} failed`
    return '☁ Upload all'
  }

  async startUpload() {
    if (!this.canUpload) return

    this.isUploading  = true
    this.successCount = 0
    this.failedCount  = 0

    const filesToUpload = this.readyFiles
    const total         = filesToUpload.length

    // Step 1 — create batch
    this.uploadService.startBatch(this.uploadedBy, total).subscribe({
      next: async (res) => {
        this.currentBatchId = res.batch_id
        await this.uploadSequentially(filesToUpload)
      },
      error: () => {
        // If batch creation fails, upload without batch_id
        this.uploadSequentially(filesToUpload)
      }
    })
  }

  private uploadSequentially(files: QueueFile[]): Promise<void> {
    return files.reduce((chain, queueFile) => {
      return chain.then(() => this.uploadOne(queueFile))
    }, Promise.resolve())
  }

  private uploadOne(queueFile: QueueFile): Promise<void> {
    return new Promise<void>(resolve => {
      queueFile.status   = 'uploading'
      queueFile.progress = 0
      queueFile.error    = ''

      this.uploadService.uploadFile(
        queueFile.file,
        this.currentBatchId ?? 0
      ).subscribe({
        next: (progress) => {
          queueFile.progress = progress.percent
          if (progress.done) {
            queueFile.status = 'done'
            this.successCount++
            resolve(undefined)
          }
          if (progress.error) {
            queueFile.status = 'failed'
            queueFile.error  = 'Upload failed'
            this.failedCount++
            resolve(undefined)
          }
        },
        error: () => {
          queueFile.status = 'failed'
          queueFile.error  = 'Upload failed'
          this.failedCount++
          resolve(undefined)
        },
        complete: () => {
          if (queueFile.status === 'uploading') resolve(undefined)
        }
      })
    }).then(() => {
      // Check if all uploads are done
      const allDone = this.queue.every(
        f => f.status === 'done' || f.status === 'failed'
      )
      if (allDone) {
        this.finishBatch()
      }
    })
  }

  private finishBatch() {
    this.isUploading = false

    if (this.currentBatchId) {
      this.uploadService.updateBatch(
        this.currentBatchId,
        this.successCount,
        this.failedCount
      ).subscribe()
    }

    // Reload history so new batch appears
    this.loadBatches()
  }

  // ── History ───────────────────────────────────────

  loadBatches() {
    this.batchesLoading = true
    this.uploadService.getBatches().subscribe({
      next:  (batches) => {
        this.batches        = batches
        this.batchesLoading = false
      },
      error: () => { this.batchesLoading = false }
    })
  }

  toggleBatchDetail(batchId: number) {
    if (this.expandedBatchId === batchId) {
      this.expandedBatchId = null
      return
    }
    this.expandedBatchId = batchId

    // Only fetch if not already loaded
    if (!this.batchDetails[batchId]) {
      this.batchDetailLoading = true
      this.uploadService.getBatchDetail(batchId).subscribe({
        next: (detail) => {
          this.batchDetails[batchId] = detail
          this.batchDetailLoading    = false
        },
        error: () => { this.batchDetailLoading = false }
      })
    }
  }

  // ── Display helpers ───────────────────────────────

  getFileSizeMB(file: File): string {
    return (file.size / (1024 * 1024)).toFixed(1) + ' MB'
  }

  getBatchDate(dateStr: string): string {
    const date  = new Date(dateStr)
    const now   = new Date()
    const diff  = now.getTime() - date.getTime()
    const days  = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) return `Today, ${date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
    if (days === 1) return `Yesterday, ${date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      + ', ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  }

  getBatchSummaryClass(batch: UploadBatch): string {
    if (batch.failed === 0) return 'batch-ok'
    if (batch.success === 0) return 'batch-fail'
    return 'batch-partial'
  }

  get historyBadgeCount(): number {
    return this.batches.length
  }
}