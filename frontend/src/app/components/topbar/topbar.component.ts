import { Component } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterModule, Router } from '@angular/router'

@Component({
  selector: 'app-topbar',
  templateUrl: './topbar.component.html',
  styleUrls: ['./topbar.component.scss'],
  standalone: true,
  imports: [CommonModule, RouterModule]
})
export class TopbarComponent {
  navItems = [
    { label: 'Browse',       route: '/'                   },
    { label: 'Upload',       route: '/upload'             },
    { label: 'Review queue', route: '/admin/corrections'  },
    { label: 'Stats',        route: '/analytics/stats'    },
  ]

  constructor(public router: Router) {}

  isActive(route: string): boolean {
    return this.router.url === route
  }
}
