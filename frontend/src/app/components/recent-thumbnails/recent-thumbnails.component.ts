import { Component, Input } from '@angular/core'
import { Image } from '../../models'
import { CommonModule } from '@angular/common'

@Component({
  selector: 'app-recent-thumbnails',
  templateUrl: './recent-thumbnails.component.html',
  styleUrls: ['./recent-thumbnails.component.scss'],
  standalone: true,
  imports: [
    CommonModule
  ],
})
export class RecentThumbnailsComponent {
  @Input() images: Image[] = []

  getYear(dateTaken: string): string {
    if (!dateTaken) return ''
    return new Date(dateTaken).getFullYear().toString()
  }

  getImageUrl(image: Image): string {
    // In local dev, images are served via Express
    // storage_url is a relative path like "Various_A/photo1.jpg"
    return `http://localhost:3000/api/images/${image.id}/file`
  }
}
