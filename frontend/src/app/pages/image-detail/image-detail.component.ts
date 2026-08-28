import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterModule, ActivatedRoute, Router } from '@angular/router'
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
  imgFailed:     boolean            = false

  // Similar images pagination
  simPage:  number = 1
  simLimit: number = 10

  constructor(
    private route:         ActivatedRoute,
    private router:        Router,
    private imagesService: ImagesService
  ) {}

  ngOnInit() {
    this.route.params.subscribe(params => {
      const id = Number(params['id'])
      this.loadImage(id)
    })
  }

  loadImage(id: number) {
    this.loading   = true
    this.imgFailed = false
    this.error     = ''
    this.simPage   = 1

    this.imagesService.getImageById(id).subscribe({
      next: (image) => {
        this.image   = image
        this.loading = false
        this.loadSimilarImages(id)
      },
      error: () => {
        this.error   = 'Image not found'
        this.loading = false
      }
    })
  }

  loadSimilarImages(id: number) {
    this.imagesService.getSimilarImages(id).subscribe({
      next: (images) => { this.similarImages = images },
      error: () => { this.similarImages = [] }
    })
  }

  // Paginated slice of similar images
  get pagedSimilarImages(): Image[] {
    const start = (this.simPage - 1) * this.simLimit
    return this.similarImages.slice(start, start + this.simLimit)
  }

  get simPages(): number {
    return Math.ceil(this.similarImages.length / this.simLimit)
  }

  simPrev() { if (this.simPage > 1) this.simPage-- }
  simNext() { if (this.simPage < this.simPages) this.simPage++ }

  get imageUrl(): string {
    return this.image ? `${environment.apiUrl}/images/${this.image.id}/file` : ''
  }

  get downloadUrl(): string {
    return this.image ? `${environment.apiUrl}/images/${this.image.id}/file?download=true` : ''
  }

  getSimilarImageUrl(image: any): string {
    return `${environment.apiUrl}/images/${image.id}/file`
  }

  onImgError(event: Event) {
    const img = event.target as HTMLImageElement
    img.style.display = 'none'
  }

  onMainImgError(event: Event) {
    const img = event.target as HTMLImageElement
    img.style.display = 'none'
    this.imgFailed = true
  }

  onSimilarClick(image: any) {
    this.router.navigate(['/images', image.id])
  }

  downloadImage() {
    if (!this.image) return
    const link    = document.createElement('a')
    link.href     = this.downloadUrl
    link.download = this.image.filename
    link.click()
  }

  goBack() {
    this.router.navigate(['/results'])
  }

  get tags(): string[] {
    if (!this.image?.tags) return []
    try {
      const parsed = typeof this.image.tags === 'string'
        ? JSON.parse(this.image.tags)
        : this.image.tags
      return parsed.map((t: any) => t.tag || t)
    } catch { return [] }
  }

  get categories(): string[] {
    if (!this.image?.categories) return []
    try {
      const parsed = typeof this.image.categories === 'string'
        ? JSON.parse(this.image.categories)
        : this.image.categories
      return parsed.map((c: any) => c.category || c)
    } catch { return [] }
  }

  get qualityWidth(): string {
    return ((this.image?.overall_score ?? 0) * 100).toFixed(0) + '%'
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—'
    try {
      return new Date(dateStr).toLocaleDateString('en-GB', {
        day: 'numeric', month: 'short', year: 'numeric'
      })
    } catch { return dateStr }
  }
}