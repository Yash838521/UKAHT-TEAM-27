import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterModule } from '@angular/router'
import { forkJoin, of } from 'rxjs'
import { catchError } from 'rxjs/operators'
import { StatsService } from '../../services/stats.service'
import { StatsResponse, AccuracyResponse } from '../../models'

@Component({
  selector: 'app-stats',
  templateUrl: './stats.component.html',
  styleUrls: ['./stats.component.scss'],
  standalone: true,
  imports: [CommonModule, RouterModule]
})
export class StatsComponent implements OnInit {

  stats:    StatsResponse | null   = null
  accuracy: AccuracyResponse | null = null
  loading:  boolean                = true
  error:    string                 = ''

  constructor(private statsService: StatsService) {}

  ngOnInit() {
    forkJoin({
      stats:    this.statsService.getDatasetStats().pipe(catchError(() => of(null))),
      accuracy: this.statsService.getAccuracy().pipe(catchError(() => of(null)))
    }).subscribe(({ stats, accuracy }) => {
      this.stats    = stats
      this.accuracy = accuracy
      this.loading  = false
    })
  }

  // ── Summary card helpers ──────────────────────────

  get totalImages(): number {
    return this.stats?.total_images ?? 0
  }

  get uniqueImages(): number {
    return this.totalImages - (this.stats?.duplicates?.in_clusters ?? 0)
  }

  get aiTaggedPct(): string {
    if (!this.stats) return '—'
    const pct = (this.stats.verification.total_tagged / this.stats.total_images) * 100
    return pct.toFixed(0) + '%'
  }

  get verifiedPct(): string {
    if (!this.stats) return '—'
    const { verified, total_tagged } = this.stats.verification
    if (!total_tagged) return '0%'
    return ((verified / total_tagged) * 100).toFixed(0) + '%'
  }

  get duplicateRate(): string {
    if (!this.stats) return '—'
    const pct = (this.stats.duplicates.in_clusters / this.stats.total_images) * 100
    return pct.toFixed(0) + '%'
  }

  // ── Bar chart helpers ─────────────────────────────

  get maxPerYear(): number {
    if (!this.stats?.per_year?.length) return 1
    return Math.max(...this.stats.per_year.map(y => y.count))
  }

  barWidth(value: number, max: number): string {
    return max === 0 ? '0%' : ((value / max) * 100).toFixed(1) + '%'
  }

  get maxPeopleDist(): number {
    if (!this.stats?.people_dist?.length) return 1
    return Math.max(...this.stats.people_dist.map(p => p.count))
  }

  peopleLabel(count: number): string {
    if (count === 0) return 'None'
    if (count === 1) return '1 person'
    return `${count} people`
  }

  // ── Scene donut helpers ───────────────────────────

  get totalSceneImages(): number {
    return this.stats?.scene_types?.reduce((s, t) => s + t.count, 0) ?? 0
  }

  scenePercent(count: number): number {
    const total = this.totalSceneImages
    return total === 0 ? 0 : (count / total) * 100
  }

  // SVG donut — circumference of r=30 is ~188.5
  get donutDasharray(): string {
    if (!this.stats?.scene_types?.length) return '0 188'
    const ext   = this.stats.scene_types.find(s => s.scene_type === 'exterior')?.count ?? 0
    const total = this.totalSceneImages
    const arc   = total === 0 ? 0 : (ext / total) * 188.5
    return `${arc.toFixed(1)} 188.5`
  }

  get donutOffsetInterior(): string {
    if (!this.stats?.scene_types?.length) return '0'
    const ext   = this.stats.scene_types.find(s => s.scene_type === 'exterior')?.count ?? 0
    const total = this.totalSceneImages
    const arc   = total === 0 ? 0 : (ext / total) * 188.5
    return `-${arc.toFixed(1)}`
  }

  get interiorDasharray(): string {
    if (!this.stats?.scene_types?.length) return '0 188'
    const int   = this.stats.scene_types.find(s => s.scene_type === 'interior')?.count ?? 0
    const total = this.totalSceneImages
    const arc   = total === 0 ? 0 : (int / total) * 188.5
    return `${arc.toFixed(1)} 188.5`
  }

  // ── Metadata completeness ─────────────────────────

  completenessPct(has: number): string {
    const total = this.stats?.completeness?.total ?? 0
    if (!total) return '0%'
    return ((has / total) * 100).toFixed(0) + '%'
  }

  completenessWidth(has: number): string {
    const total = this.stats?.completeness?.total ?? 0
    if (!total) return '0%'
    return ((has / total) * 100).toFixed(1) + '%'
  }

  aiTaggedWidth(): string {
    if (!this.stats) return '0%'
    const pct = (this.stats.verification.total_tagged / this.stats.total_images) * 100
    return pct.toFixed(1) + '%'
  }

  verifiedWidth(): string {
    if (!this.stats) return '0%'
    const { verified, total_tagged } = this.stats.verification
    if (!total_tagged) return '0%'
    return ((verified / total_tagged) * 100).toFixed(1) + '%'
  }

  // ── Accuracy helpers ──────────────────────────────

  get sceneCorrections(): number {
    return this.accuracy?.per_field?.find(f => f.field_name === 'scene_type')?.corrections ?? 0
  }

  get peopleCorrections(): number {
    return this.accuracy?.per_field?.find(f => f.field_name === 'people_count')?.corrections ?? 0
  }

  get maxSceneConfusion(): number {
    if (!this.accuracy?.scene_accuracy?.length) return 1
    return Math.max(...this.accuracy.scene_accuracy.map(s => s.count))
  }

  confusionLabel(row: { predicted: string; actual: string }): string {
    const p = row.predicted ? row.predicted.charAt(0).toUpperCase() + row.predicted.slice(0, 3) : '?'
    const a = row.actual    ? row.actual.charAt(0).toUpperCase()    + row.actual.slice(0, 3)    : '?'
    return `${p} → ${a}`
  }

  // ── Downloads ─────────────────────────────────────

  downloadCSV() {
    if (!this.stats) return

    const lines: string[] = []
    const now = new Date().toLocaleDateString('en-GB')

    lines.push(`UKAHT Image Archive — Dataset Statistics`)
    lines.push(`Generated,${now}`)
    lines.push('')

    // Summary
    lines.push('SUMMARY')
    lines.push(`Total images,${this.stats.total_images}`)
    lines.push(`Unique images,${this.uniqueImages}`)
    lines.push(`Duplicate images,${this.stats.duplicates.in_clusters}`)
    lines.push(`Duplicate clusters,${this.stats.duplicates.total_clusters}`)
    lines.push(`AI tagged,${this.stats.verification.total_tagged}`)
    lines.push(`Human verified,${this.stats.verification.verified}`)
    lines.push('')

    // Per year
    lines.push('IMAGES PER YEAR')
    lines.push('Year,Count')
    this.stats.per_year.forEach(y => lines.push(`${y.year},${y.count}`))
    lines.push('')

    // Scene types
    lines.push('SCENE TYPES')
    lines.push('Scene,Count')
    this.stats.scene_types.forEach(s => lines.push(`${s.scene_type},${s.count}`))
    lines.push('')

    // Quality
    lines.push('QUALITY DISTRIBUTION')
    lines.push(`High (>=0.70),${this.stats.quality.high}`)
    lines.push(`Medium (0.40-0.70),${this.stats.quality.medium}`)
    lines.push(`Low (<0.40),${this.stats.quality.low}`)
    lines.push('')

    // Metadata
    lines.push('METADATA COMPLETENESS')
    lines.push(`Has date taken,${this.completenessPct(this.stats.completeness.has_date)}`)
    lines.push(`Has camera model,${this.completenessPct(this.stats.completeness.has_camera)}`)
    lines.push(`Has GPS,${this.completenessPct(this.stats.completeness.has_gps)}`)
    lines.push('')

    // Cameras
    lines.push('TOP CAMERAS')
    lines.push('Model,Make,Count')
    this.stats.cameras.slice(0, 10).forEach(c =>
      lines.push(`${c.camera_model},${c.camera_make},${c.count}`)
    )
    lines.push('')

    // People distribution
    lines.push('PEOPLE PER IMAGE')
    lines.push('People count,Images')
    this.stats.people_dist.forEach(p =>
      lines.push(`${p.people_count},${p.count}`)
    )
    lines.push('')

    // Accuracy
    if (this.accuracy) {
      lines.push('AI ACCURACY')
      lines.push(`Total corrections,${this.accuracy.total_corrections}`)
      lines.push(`Scene type corrections,${this.sceneCorrections}`)
      lines.push(`People count corrections,${this.peopleCorrections}`)
      lines.push(`People count MAE,${this.accuracy.people_mae != null ? Number(this.accuracy.people_mae).toFixed(2) : 'N/A'}`)
    }

    // Trigger download
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `ukaht-stats-${now.replace(/\//g, '-')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  downloadPDF() {
    window.print()
  }
}