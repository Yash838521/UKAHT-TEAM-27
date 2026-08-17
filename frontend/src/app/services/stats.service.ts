import { Injectable } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Observable } from 'rxjs'
import { environment } from '../../../environments/environment'
import { StatsResponse, AccuracyResponse } from '../models'

@Injectable({ providedIn: 'root' })
export class StatsService {
  private base = environment.apiUrl

  constructor(private http: HttpClient) {}

  getDatasetStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.base}/stats/dataset`)
  }

  getAccuracy(): Observable<AccuracyResponse> {
    return this.http.get<AccuracyResponse>(`${this.base}/stats/accuracy`)
  }
}
