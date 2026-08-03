import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { environment } from '../../../environment'
import { CategoriesResponse, StatsResponse } from '../models'

@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  getCategories() {
    return this.http.get<CategoriesResponse>(`${this.base}/categories`)
  }

  getStats() {
    return this.http.get<StatsResponse>(`${this.base}/stats/dataset`)
  }
}
