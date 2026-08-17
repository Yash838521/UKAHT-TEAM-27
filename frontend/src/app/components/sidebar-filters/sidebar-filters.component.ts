import {
  Component, Input, Output, EventEmitter,
  OnInit, OnChanges, SimpleChanges
} from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { FilterState, TagCount } from '../../models'

interface DateOption {
  label: string
  from:  string
  to:    string
}

@Component({
  selector: 'app-sidebar-filters',
  templateUrl: './sidebar-filters.component.html',
  styleUrls: ['./sidebar-filters.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule]
})
export class SidebarFiltersComponent implements OnInit, OnChanges {
  @Input()  tags:    TagCount[]  = []
  @Input()  minYear: number      = 2010
  @Input()  maxYear: number      = 2023
  @Output() apply                = new EventEmitter<FilterState>()
  @Output() clear                = new EventEmitter<void>()

  // Internal state — sidebar owns its own copy
  sceneType:    string       = ''
  peopleMin:    number | null = null
  qualityMin:   number       = 0
  qualityDisplay: number     = 0
  dateFrom:     string       = ''
  dateTo:       string       = ''
  noDuplicates: boolean      = false
  selectedTags: string[]     = []
  tagSearch:    string       = ''
  dateOptions:  DateOption[] = []

  sceneOptions = [
    { label: 'All',      value: ''         },
    { label: 'Exterior', value: 'exterior' },
    { label: 'Interior', value: 'interior' },
  ]

  peopleOptions = [
    { label: 'Any',       value: null },
    { label: '1 or more', value: 1    },
    { label: '3 or more', value: 3    },
    { label: 'None',      value: 0    },
  ]

  ngOnInit() {
    this.buildDateOptions()
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['minYear'] || changes['maxYear']) {
      this.buildDateOptions()
    }
  }

  buildDateOptions() {
    const options: DateOption[] = [
      { label: 'All years', from: '', to: '' }
    ]
    const decadeStart = Math.floor(this.minYear / 10) * 10
    const decadeEnd   = Math.floor(this.maxYear / 10) * 10

    for (let decade = decadeStart; decade <= decadeEnd; decade += 10) {
      const from = Math.max(decade,     this.minYear)
      const to   = Math.min(decade + 9, this.maxYear)
      options.push({
        label: `${from}–${to}`,
        from:  `${from}-01-01`,
        to:    `${to}-12-31`
      })
    }
    this.dateOptions = options
  }

  get filteredTags(): TagCount[] {
    if (!this.tagSearch) return this.tags
    return this.tags.filter(t =>
      t.tag.toLowerCase().includes(this.tagSearch.toLowerCase())
    )
  }

  isTagSelected(tag: string): boolean {
    return this.selectedTags.includes(tag)
  }

  setScene(value: string) {
    console.log('scene');
    this.sceneType = value
  }

  setPeople(value: number | null) {
    this.peopleMin = value
  }

  setDuplicates(value: boolean) {
    this.noDuplicates = value
  }

  toggleTag(tag: string) {
    const idx = this.selectedTags.indexOf(tag)
    if (idx > -1) {
      this.selectedTags = this.selectedTags.filter(t => t !== tag)
    } else {
      this.selectedTags = [...this.selectedTags, tag]
    }
  }

  onQualityChange(event: Event) {
    const val           = +(event.target as HTMLInputElement).value / 100
    this.qualityMin     = Math.round(val * 100) / 100
    this.qualityDisplay = this.qualityMin
  }

  setDate(from: string, to: string) {
    this.dateFrom = from
    this.dateTo   = to
  }

  isDateActive(from: string, to: string): boolean {
    return this.dateFrom === from && this.dateTo === to
  }

onApply() {
  const filterState: FilterState = {
    scene_type:    this.sceneType,
    people_min:    this.peopleMin,
    quality_min:   this.qualityMin,
    date_from:     this.dateFrom,
    date_to:       this.dateTo,
    no_duplicates: this.noDuplicates,
    tags:          [...this.selectedTags],
    category:      '',              // ← add this
    sort:          'overall_score',
    order:         'DESC',
    page:          1,
    limit:         24
  }
  this.apply.emit(filterState)
}

  onClear() {
    this.sceneType     = ''
    this.peopleMin     = null
    this.qualityMin    = 0
    this.qualityDisplay = 0
    this.dateFrom      = ''
    this.dateTo        = ''
    this.noDuplicates  = false
    this.selectedTags  = []
    this.tagSearch     = ''
    this.clear.emit()
  }
}
