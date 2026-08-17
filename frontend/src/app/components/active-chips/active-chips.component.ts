import { Component, Input, Output, EventEmitter } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FilterState } from '../../models'

interface Chip {
  label: string
  type:  'filter' | 'tag'
  key:   string
  value: any
}

@Component({
  selector: 'app-active-chips',
  templateUrl: './active-chips.component.html',
  styleUrls: ['./active-chips.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class ActiveChipsComponent {
  @Input()  filters!: FilterState
  @Output() removeFilter = new EventEmitter<{ key: string; value: any }>()
  @Output() clearAll     = new EventEmitter<void>()

  get chips(): Chip[] {
    const chips: Chip[] = []

    // Category from home page card click
    if (this.filters.category) {
      chips.push({
        label: this.filters.category,
        type: 'filter', key: 'category', value: ''
      })
    }

    if (this.filters.scene_type) {
      chips.push({
        label: this.filters.scene_type.charAt(0).toUpperCase() + this.filters.scene_type.slice(1),
        type: 'filter', key: 'scene_type', value: ''
      })
    }

    if (this.filters.people_min !== null && this.filters.people_min !== undefined) {
      const label = this.filters.people_min === 0
        ? 'No people'
        : `People ${this.filters.people_min}+`
      chips.push({ label, type: 'filter', key: 'people_min', value: null })
    }

    if (this.filters.quality_min > 0) {
      chips.push({
        label: `Quality ${this.filters.quality_min.toFixed(2)}+`,
        type: 'filter', key: 'quality_min', value: 0
      })
    }

    if (this.filters.date_from) {
      const from = this.filters.date_from.substring(0, 4)
      const to   = this.filters.date_to.substring(0, 4)
      chips.push({
        label: `${from}–${to}`,
        type: 'filter', key: 'date_from', value: ''
      })
    }

    if (this.filters.no_duplicates) {
      chips.push({
        label: 'Unique only',
        type: 'filter', key: 'no_duplicates', value: false
      })
    }

    this.filters.tags.forEach(tag => {
      chips.push({ label: tag, type: 'tag', key: 'tag', value: tag })
    })

    return chips
  }

  get hasChips(): boolean {
    return this.chips.length > 0
  }

  remove(chip: Chip) {
    this.removeFilter.emit({ key: chip.key, value: chip.value })
  }

  onClearAll() {
    this.clearAll.emit()
  }
}
