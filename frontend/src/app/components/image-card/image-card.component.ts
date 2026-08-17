import { Component, Input, Output, EventEmitter } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Image } from '../../models'
import { environment } from '../../../../environments/environment'

@Component({
  selector: 'app-image-card',
  templateUrl: './image-card.component.html',
  styleUrls: ['./image-card.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class ImageCardComponent {
  @Input()  image!:      Image
  @Input()  similarity?: number
  @Output() cardClick  = new EventEmitter<Image>()

  imgFailed = false

  get imageUrl(): string {
    return `${environment.apiUrl}/images/${this.image.id}/file`
  }

  onImgError(event: Event) {
    // Hide broken img tag and show placeholder icon instead
    const img = event.target as HTMLImageElement
    img.style.display = 'none'
    this.imgFailed = true
  }

  onClick() {
    this.cardClick.emit(this.image)
  }

  get peopleLabel(): string {
    if (!this.image.people_count) return 'No people'
    return this.image.people_count === 1
      ? '1 person'
      : `${this.image.people_count} people`
  }

  get qualityScore(): string {
    if (!this.image.overall_score) return '—'
    return this.image.overall_score.toFixed(2)
  }

  get similarityLabel(): string {
    if (!this.similarity) return ''
    return (this.similarity * 100).toFixed(0) + '% match'
  }
}
