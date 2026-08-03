import { Component, Input, Output, EventEmitter } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Image } from '../../models'
import { ImageCardComponent } from '../image-card/image-card.component'

@Component({
  selector: 'app-image-grid',
  templateUrl: './image-grid.component.html',
  styleUrls: ['./image-grid.component.scss'],
  standalone: true,
  imports: [CommonModule, ImageCardComponent]
})
export class ImageGridComponent {
  @Input()  images:       Image[]                 = []
  @Input()  similarities: Record<number, number>  = {}
  @Input()  loading:      boolean                 = false
  @Input()  total:        number                  = 0
  @Input()  pages:        number                  = 0
  @Input()  currentPage:  number                  = 1
  @Output() imageClick   = new EventEmitter<Image>()
  @Output() pageChange   = new EventEmitter<number>()

  get pageNumbers(): (number | string)[] {
    if (this.pages <= 7) {
      return Array.from({ length: this.pages }, (_, i) => i + 1)
    }
    const result: (number | string)[] = [1]
    if (this.currentPage > 3) result.push('...')
    for (
      let i = Math.max(2, this.currentPage - 1);
      i <= Math.min(this.pages - 1, this.currentPage + 1);
      i++
    ) {
      result.push(i)
    }
    if (this.currentPage < this.pages - 2) result.push('...')
    result.push(this.pages)
    return result
  }

  onImageClick(image: Image) {
    this.imageClick.emit(image)
  }

  onPageClick(page: number | string) {
    if (typeof page === 'number') {
      this.pageChange.emit(page)
    }
  }

  getSimilarity(imageId: number): number | undefined {
    return this.similarities[imageId]
  }
}
