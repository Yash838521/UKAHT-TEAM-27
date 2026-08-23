import { Component, Input } from '@angular/core'
import { CommonModule } from '@angular/common'

@Component({
  selector: 'app-footer-stats',
  templateUrl: './footer-stats.component.html',
  styleUrls: ['./footer-stats.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class FooterStatsComponent {
  @Input() totalImages: number = 0
  @Input() uniqueImages: number = 0
  @Input() dateRange: string = ''
  @Input() pending: number = 0
}
