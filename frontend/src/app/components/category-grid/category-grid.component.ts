import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Category } from '../../models'
import { CategoryCardComponent } from '../category-card/category-card.component'

interface CategoryConfig {
  name:  string
  count: number
  icon:  string
  color: string
}

@Component({
  selector: 'app-category-grid',
  templateUrl: './category-grid.component.html',
  styleUrls: ['./category-grid.component.scss'],
  standalone: true,
  imports: [CommonModule, CategoryCardComponent]
})
export class CategoryGridComponent implements OnChanges {
  @Input() categories: Category[] = []
  @Output() categoryClick = new EventEmitter<string>()

  // Icon and colour config per category name
  private displayConfig: Record<string, { icon: string; color: string }> = {
    'Exterior':     { icon: '🏔',  color: '#378add' },
    'Interior':     { icon: '🏠',  color: '#1d9e75' },
    'People':       { icon: '👥',  color: '#ba7517' },
    'Equipment':    { icon: '🔧',  color: '#993556' },
    'Best quality': { icon: '⭐',  color: '#534ab7' },
    'By decade':    { icon: '📅',  color: '#d85a30' },
    'Camp life':    { icon: '⛺',  color: '#3b6d11' },
    'Unique only':  { icon: '✨',  color: '#5f5e5a' },
    'Vehicles':     { icon: '🚗',  color: '#b54a1a' },
    'Landscape':    { icon: '🌨',  color: '#2a6b8a' },
  }

  enrichedCategories: CategoryConfig[] = []

  ngOnChanges(changes: SimpleChanges) {
    if (changes['categories']) {
      this.enrichedCategories = this.categories.map(cat => ({
        name:  cat.category,
        count: cat.count,
        icon:  this.displayConfig[cat.category]?.icon  ?? '📁',
        color: this.displayConfig[cat.category]?.color ?? '#4a9eff'
      }))
    }
  }

  onCategoryClick(name: string) {
    this.categoryClick.emit(name)
  }
}
