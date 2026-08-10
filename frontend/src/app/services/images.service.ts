import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { Observable } from 'rxjs'
import { environment } from '../../../environments/environment'
import { Image, ImagesResponse, TagCount, ImageDetail } from '../models'

@Injectable({ providedIn: 'root' })
export class ImagesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  // Home page — recently uploaded strip
  getRecent(limit: number = 10): Observable<Image[]> {
    return this.http.get<Image[]>(`${this.base}/images/recent`, {
      params: new HttpParams().set('limit', limit)
    })
  }

  // Browse page — filtered image grid
  getImages(filters: Record<string, any> = {}): Observable<ImagesResponse> {
    let params = new HttpParams()
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '' && val !== false) {
        params = params.set(key, String(val))
      }
    })
    return this.http.get<ImagesResponse>(`${this.base}/images`, { params })
  }

  // Browse page — CLIP semantic search
  search(query: string, filters: Record<string, any> = {}): Observable<any> {
    let params = new HttpParams().set('q', query)
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        params = params.set(key, String(val))
      }
    })
    return this.http.get<any>(`${this.base}/search`, { params })
  }

  // Browse page sidebar — object tag counts
  getTagCounts(): Observable<TagCount[]> {
    return this.http.get<TagCount[]>(`${this.base}/stats/tags`)
  }

  // Image detail page — full metadata for one image
getImageById(id: number): Observable<ImageDetail> {
  return this.http.get<ImageDetail>(`${this.base}/images/${id}`)
}

// Image detail page — other images in same duplicate cluster
getSimilarImages(id: number): Observable<Image[]> {
  return this.http.get<Image[]>(`${this.base}/images/${id}/similar`)
}
}
