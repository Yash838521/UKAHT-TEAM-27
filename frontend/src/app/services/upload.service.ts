import { Injectable } from '@angular/core'
import { HttpClient, HttpRequest, HttpEventType, HttpResponse } from '@angular/common/http'
import { Observable, Subject } from 'rxjs'
import { environment } from '../../../environments/environment'
import { UploadBatch, BatchDetail } from '../models'

export interface UploadProgress {
  percent:  number
  done:     boolean
  error:    boolean
  imageId?: number
}

@Injectable({ providedIn: 'root' })
export class UploadService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  // ── Batch management ──────────────────────────────

  // Start a new upload batch — returns batch_id
  startBatch(uploadedBy: string, totalFiles: number): Observable<{ batch_id: number }> {
    return this.http.post<{ batch_id: number }>(
      `${this.base}/upload/batch/start`,
      { uploaded_by: uploadedBy, total_files: totalFiles }
    )
  }

  // Update batch success/failed counts after all uploads complete
  updateBatch(batchId: number, success: number, failed: number): Observable<any> {
    return this.http.patch(
      `${this.base}/upload/batch/${batchId}`,
      { success, failed }
    )
  }

  // ── History ───────────────────────────────────────

  // Get all upload batches for history tab
  getBatches(): Observable<UploadBatch[]> {
    return this.http.get<UploadBatch[]>(`${this.base}/upload/batches`)
  }

  // Get images in a specific batch
  getBatchDetail(batchId: number): Observable<BatchDetail> {
    return this.http.get<BatchDetail>(`${this.base}/upload/batches/${batchId}`)
  }

  // ── File upload ───────────────────────────────────

  // Upload a single file with progress tracking
  // Returns Observable that emits progress updates
  uploadFile(file: File, batchId: number): Observable<UploadProgress> {
    const subject = new Subject<UploadProgress>()

    const formData = new FormData()
    formData.append('image', file)
    formData.append('batch_id', String(batchId))

    const req = new HttpRequest('POST', `${this.base}/upload`, formData, {
      reportProgress: true
    })

    this.http.request(req).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress) {
          const percent = event.total
            ? Math.round((event.loaded / event.total) * 100)
            : 0
          subject.next({ percent, done: false, error: false })
        }
        if (event instanceof HttpResponse) {
          const body = event.body as any
          subject.next({
            percent:  100,
            done:     true,
            error:    false,
            imageId:  body?.image_id
          })
          subject.complete()
        }
      },
      error: () => {
        subject.next({ percent: 0, done: false, error: true })
        subject.complete()
      }
    })

    return subject.asObservable()
  }
}
