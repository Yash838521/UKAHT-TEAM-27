import { Injectable } from '@angular/core'
import { HttpClient, HttpRequest, HttpEventType, HttpResponse } from '@angular/common/http'
import { Observable, Subject, lastValueFrom } from 'rxjs'
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

  startBatch(uploadedBy: string, totalFiles: number): Observable<{ batch_id: number }> {
    return this.http.post<{ batch_id: number }>(
      `${this.base}/upload/batch/start`,
      { uploaded_by: uploadedBy, total_files: totalFiles }
    )
  }

  updateBatch(batchId: number, success: number, failed: number): Observable<any> {
    return this.http.patch(
      `${this.base}/upload/batch/${batchId}`,
      { success, failed }
    )
  }

  getBatches(): Observable<UploadBatch[]> {
    return this.http.get<UploadBatch[]>(`${this.base}/upload/batches`)
  }

  getBatchDetail(batchId: number): Observable<BatchDetail> {
    return this.http.get<BatchDetail>(`${this.base}/upload/batches/${batchId}`)
  }

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
            ? Math.round((event.loaded / event.total) * 80)
            : 0
          subject.next({ percent, done: false, error: false })
        }

        if (event instanceof HttpResponse) {
          const body = event.body as any

          if (body?.mode === 's3') {
            // S3 mode — upload to S3 then confirm
            subject.next({ percent: 80, done: false, error: false })

            fetch(body.upload_url, {
              method:  'PUT',
              body:    file,
              headers: { 'Content-Type': file.type }
            })
            .then(() => {
              subject.next({ percent: 90, done: false, error: false })
              return lastValueFrom(this.http.post(`${this.base}/upload/confirm-s3`, {
                filename:    body.filename,
                storage_url: body.storage_url,
                batch_id:    body.batch_id,
                image_uid:   body.image_uid
              }))
            })
            .then((confirm: any) => {
              subject.next({ percent: 100, done: true, error: false, imageId: confirm?.image_id })
              subject.complete()
            })
            .catch(() => {
              subject.next({ percent: 0, done: false, error: true })
              subject.complete()
            })

          } else {
            // Local mode — done
            subject.next({ percent: 100, done: true, error: false, imageId: body?.image_id })
            subject.complete()
          }
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