import { Injectable } from '@angular/core'
import { HttpClient, HttpParams } from '@angular/common/http'
import { environment } from '../../../environment'
import { Image } from '../models'

@Injectable({ providedIn: 'root' })
export class ImagesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  getRecent(limit: number = 10) {
    return this.http.get<Image[]>(`${this.base}/images/recent`, {
      params: new HttpParams().set('limit', limit)
    })
  }

  getImages(filters: Record<string, any> = {}) {
    let params = new HttpParams()
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        params = params.set(key, val)
      }
    })
    return this.http.get<{ total: number; images: Image[] }>(`${this.base}/images`, { params })
  }
}
