import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { environment } from '../../../environments/environment'
import { Image, TagCount } from '../models'
import { Observable } from 'rxjs'

export interface ImagesResponse {
  total:  number
  page:   number
  limit:  number
  pages:  number
  images: Image[]
}

@Injectable({ providedIn: 'root' })
export class ImagesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  getRecent(limit: number = 10): Observable<Image[]> {
    return this.http.get<Image[]>(`${this.base}/images/recent`, {
      params: new HttpParams().set('limit', limit)
    })
  }

  // Fix 4 — return type now includes pages
  getImages(filters: Record<string, any> = {}): Observable<ImagesResponse> {
    let params = new HttpParams()
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        params = params.set(key, String(val))
      }
    })
    return this.http.get<ImagesResponse>(`${this.base}/images`, { params })
  }

  search(query: string, filters: Record<string, any> = {}): Observable<any> {
    let params = new HttpParams().set('q', query)
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        params = params.set(key, String(val))
      }
    })
    return this.http.get<any>(`${this.base}/search`, { params })
  }

  getTagCounts(): Observable<TagCount[]> {
    return this.http.get<TagCount[]>(`${this.base}/stats/tags`)
  }
}
