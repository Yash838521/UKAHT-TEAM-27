import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Observable } from 'rxjs'
import { environment } from '../../../environments/environment'
import { CategoriesResponse, StatsResponse } from '../models'

@Injectable({ providedIn: 'root' })
export class CategoriesService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  // Home page — category cards with counts
  getCategories(): Observable<CategoriesResponse> {
    return this.http.get<CategoriesResponse>(`${this.base}/categories`)
  }

  // Home page footer stats + browse page year range
  getStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.base}/stats/dataset`)
  }
}
