import { Component, Input } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Image } from '../../models'
import { environment } from '../../../../environments/environment'

@Component({
  selector: 'app-recent-thumbnails',
  templateUrl: './recent-thumbnails.component.html',
  styleUrls: ['./recent-thumbnails.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class RecentThumbnailsComponent {
  @Input() images: Image[] = []

  getYear(dateTaken: string): string {
    if (!dateTaken) return '—'
    try {
      return new Date(dateTaken).getFullYear().toString()
    } catch {
      return '—'
    }
  }

  getSceneLabel(image: Image): string {
    if (!image.scene_type) return 'Unknown'
    return image.scene_type.charAt(0).toUpperCase() + image.scene_type.slice(1)
  }

  getImageUrl(image: Image): string {
    return `${environment.apiUrl}/images/${image.id}/file`
  }
}
