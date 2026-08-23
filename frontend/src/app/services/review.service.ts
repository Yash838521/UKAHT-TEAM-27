import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { environment } from '../../../environments/environment'
import { QueueResponse, ClustersResponse } from '../models'

@Injectable({ providedIn: 'root' })
export class ReviewService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  // ── Tag review ────────────────────────────────────────────────────────────

  // GET /api/corrections/queue — low confidence images pending review
  getQueue(page: number = 1, limit: number = 20): Observable<QueueResponse> {
    return this.http.get<QueueResponse>(`${this.base}/corrections/queue`, {
      params: new HttpParams().set('page', page).set('limit', limit)
    })
  }

  // POST /api/corrections/confirm — mark AI tags as correct without changes
  confirmTags(imageId: number, reviewer: string): Observable<any> {
    return this.http.post(`${this.base}/corrections/confirm`, {
      image_id: imageId,
      reviewer
    })
  }

  // POST /api/corrections — save a field correction
  saveCorrection(
    imageId:   number,
    fieldName: string,
    aiValue:   string,
    humanValue: string,
    reviewer:  string
  ): Observable<any> {
    return this.http.post(`${this.base}/corrections`, {
      image_id:    imageId,
      field_name:  fieldName,
      ai_value:    aiValue,
      human_value: humanValue,
      reviewer
    })
  }

  // ── Duplicate review ──────────────────────────────────────────────────────

  // GET /api/clusters — all duplicate clusters with members
  getClusters(page: number = 1, limit: number = 10): Observable<ClustersResponse> {
    return this.http.get<ClustersResponse>(`${this.base}/clusters`, {
      params: new HttpParams().set('page', page).set('limit', limit)
    })
  }

  // PATCH /api/clusters/:clusterId/representative — set new best image
  setRepresentative(clusterId: number, imageId: number): Observable<any> {
    return this.http.patch(
      `${this.base}/clusters/${clusterId}/representative`,
      { image_id: imageId }
    )
  }

  // DELETE /api/clusters/:clusterId/image/:imageId — remove image from cluster
  removeFromCluster(
    clusterId:         number,
    imageId:           number,
    wasRepresentative: boolean
  ): Observable<any> {
    return this.http.delete(
      `${this.base}/clusters/${clusterId}/image/${imageId}`,
      { params: new HttpParams().set('was_representative', String(wasRepresentative)) }
    )
  }

  // DELETE /api/clusters/:clusterId — dissolve entire cluster
  dissolveCluster(clusterId: number): Observable<any> {
    return this.http.delete(`${this.base}/clusters/${clusterId}`)
  }
}
