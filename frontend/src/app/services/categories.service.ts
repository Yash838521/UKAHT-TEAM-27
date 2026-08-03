import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { environment } from '../../../environments/environment'
import { Observable } from 'rxjs'

export interface Category {
  category: string
  count:    number
}

export interface CategoriesResponse {
  categories:   Category[]
  total_images: number
  pending:      number
}

export interface StatsResponse {
  total_images: number
  per_year:     { year: number; count: number }[]
  scene_types:  { scene_type: string; count: number }[]
  duplicates:   { total: number; in_clusters: number; total_clusters: number }
}

@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  getCategories(): Observable<CategoriesResponse> {
    return this.http.get<CategoriesResponse>(`${this.base}/categories`)
  }

  getStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.base}/stats/dataset`)
  }
}