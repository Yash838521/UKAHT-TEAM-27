import { Component, Input, Output, EventEmitter, OnChanges } from '@angular/core'
import { Category } from '../../models'
import { CommonModule } from '@angular/common'
import { CategoryCardComponent } from '../category-card/category-card.component'

interface CategoryConfig {
  name: string
  icon: string
  color: string
  count: number
}

@Component({
  selector: 'app-category-grid',
  templateUrl: './category-grid.component.html',
  styleUrls: ['./category-grid.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    CategoryCardComponent
  ],
})
export class CategoryGridComponent implements OnChanges {
  @Input() categories: Category[] = []
  @Output() categoryClick = new EventEmitter<string>()

  // Icon and color config per category name
  private config: Record<string, { icon: string; color: string }> = {
    'Exterior':     { icon: '🏔',  color: '#378add' },
    'Interior':     { icon: '🏠',  color: '#1d9e75' },
    'People':       { icon: '👥',  color: '#ba7517' },
    'Equipment':    { icon: '🔧',  color: '#993556' },
    'Best quality': { icon: '⭐',  color: '#534ab7' },
    'By decade':    { icon: '📅',  color: '#d85a30' },
    'Camp life':    { icon: '⛺',  color: '#3b6d11' },
    'Unique only':  { icon: '✨',  color: '#5f5e5a' },
  }

  enrichedCategories: CategoryConfig[] = []

  ngOnChanges() {
    this.enrichedCategories = this.categories.map(cat => ({
      name:  cat.category,
      count: cat.count,
      icon:  this.config[cat.category]?.icon  || '📁',
      color: this.config[cat.category]?.color || '#378add'
    }))
  }

  onCategoryClick(name: string) {
    this.categoryClick.emit(name)
  }
}
