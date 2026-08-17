import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterModule, ActivatedRoute, Router } from '@angular/router'
import { forkJoin, of } from 'rxjs'
import { catchError } from 'rxjs/operators'
import { ImagesService } from '../../services/images.service'
import { ImageDetail, Image } from '../../models'
import { environment } from '../../../../environments/environment'

@Component({
  selector: 'app-image-detail',
  templateUrl: './image-detail.component.html',
  styleUrls: ['./image-detail.component.scss'],
  standalone: true,
  imports: [CommonModule, RouterModule]
})
export class ImageDetailComponent implements OnInit {
  image:         ImageDetail | null = null
  similarImages: Image[]            = []
  loading:       boolean            = true
  error:         string             = ''

  constructor(
    private imagesService: ImagesService,
    private route:         ActivatedRoute,
    private router:        Router
  ) {}

  ngOnInit() {
    this.route.paramMap.subscribe(params => {
      const id = Number(params.get('id'))
      if (!id) {
        this.error   = 'Invalid image ID'
        this.loading = false
        return
      }
      this.loadImage(id)
    })
  }

  loadImage(id: number) {
    this.loading = true
    this.error   = ''

    forkJoin({
      image: this.imagesService.getImageById(id).pipe(
        catchError(() => of(null))
      ),
      similar: this.imagesService.getSimilarImages(id).pipe(
        catchError(() => of([]))
      )
    }).subscribe(({ image, similar }) => {
      if (!image) {
        this.error   = 'Image not found'
        this.loading = false
        return
      }
      this.image         = image
      // Exclude the current image from similar list
      this.similarImages = (similar ?? []).filter(s => s.id !== id)
      this.loading       = false
    })
  }

  // ── Computed display values ───────────────────────

  get displaySceneType(): string {
    // Use human correction if available
    const scene = this.image?.corrected_scene_type ?? this.image?.scene_type
    if (!scene) return '—'
    return scene.charAt(0).toUpperCase() + scene.slice(1)
  }

  get displayPeopleCount(): string {
    const count = this.image?.corrected_people_count ?? this.image?.people_count
    if (count === null || count === undefined) return '—'
    return String(count)
  }

  get primaryCategory(): string | null {
    const cats = this.image?.categories
    if (!cats || cats.length === 0) return null
    return cats.find(c => c.is_primary)?.category ?? cats[0].category
  }

  get uploadedDate(): string {
    if (!this.image?.uploaded_at) return '—'
    return new Date(this.image.uploaded_at).toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric'
    })
  }

  get dimensions(): string {
    if (!this.image?.image_width || !this.image?.image_height) return '—'
    return `${this.image.image_width} × ${this.image.image_height}`
  }

  get qualityPercent(): number {
    return Math.round((this.image?.overall_score ?? 0) * 100)
  }

  get imageUrl(): string {
    if (!this.image) return ''
    return `${environment.apiUrl}/images/${this.image.id}/file`
  }

  get downloadUrl(): string {
    if (!this.image) return ''
    return `${environment.apiUrl}/images/${this.image.id}/file?download=true`
  }

  // ── Actions ──────────────────────────────────────

  openFullSize() {
    window.open(this.imageUrl, '_blank')
  }

  downloadImage() {
    const link    = document.createElement('a')
    link.href     = this.downloadUrl
    link.download = this.image?.filename ?? 'image'
    link.click()
  }

  onSimilarClick(image: Image) {
    this.router.navigate(['/images', image.id])
  }

  onImageError(event: Event) {
    const img = event.target as HTMLImageElement
    img.style.display = "none"
  }

  goBack() {
    window.history.back()
  }
}
