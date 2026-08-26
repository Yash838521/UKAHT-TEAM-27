import { Component, Input, Output, EventEmitter, OnInit, OnChanges } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { FilterState, TagCount } from '../../models'

interface FacetGroup {
  facet:  string
  label:  string
  tags:   TagCount[]
}

const FACET_LABELS: Record<string, string> = {
  nature:    'Nature',
  condition: 'Condition',
  shot_type: 'Shot type',
  activity:  'Activity',
  structure: 'Structure',
  room:      'Room',
  object:    'Object',
}

@Component({
  selector:    'app-sidebar-filters',
  templateUrl: './sidebar-filters.component.html',
  styleUrls:   ['./sidebar-filters.component.scss'],
  standalone:  true,
  imports:     [CommonModule, FormsModule]
})
export class SidebarFiltersComponent implements OnInit, OnChanges {
  @Input()  filters!:     FilterState
  @Input()  tags:         TagCount[] = []
  @Input()  minYear:      number     = 2010
  @Input()  maxYear:      number     = 2023
  @Output() apply  = new EventEmitter<FilterState>()
  @Output() clear  = new EventEmitter<void>()

  sceneType:    string   = ''
  peopleMin:    number | null = null
  qualityMin:   number   = 0
  dateFrom:     string   = ''
  dateTo:       string   = ''
  noDuplicates: boolean  = false
  selectedTags: string[] = []
  tagSearch:    string   = ''

  facetGroups:  FacetGroup[] = []

  sceneOptions = [
    { value: '',         label: 'Any' },
    { value: 'exterior', label: 'Exterior' },
    { value: 'interior', label: 'Interior' },
  ]

  peopleOptions = [
    { value: null, label: 'Any' },
    { value: 0,    label: 'No people' },
    { value: 1,    label: '1 or more' },
    { value: 3,    label: '3 or more (group)' },
  ]

  dateOptions = [
    { label: 'Any',         from: '', to: '' },
    { label: 'Before 2000', from: '', to: '1999-12-31' },
    { label: '2000–2009',   from: '2000-01-01', to: '2009-12-31' },
    { label: '2010–2019',   from: '2010-01-01', to: '2019-12-31' },
    { label: '2020–present',from: '2020-01-01', to: '' },
  ]

  ngOnInit() { this.syncFromFilters() }
  ngOnChanges() {
    this.syncFromFilters()
    this.buildFacetGroups()
  }

  private syncFromFilters() {
    if (!this.filters) return
    this.sceneType    = this.filters.scene_type    || ''
    this.peopleMin    = this.filters.people_min    ?? null
    this.qualityMin   = this.filters.quality_min   || 0
    this.dateFrom     = this.filters.date_from     || ''
    this.dateTo       = this.filters.date_to       || ''
    this.noDuplicates = this.filters.no_duplicates || false
    this.selectedTags = this.filters.tags          || []
  }

  private buildFacetGroups() {
    const grouped: Record<string, TagCount[]> = {}
    for (const t of this.tags) {
      const facet = (t as any).facet || 'object'
      if (!grouped[facet]) grouped[facet] = []
      grouped[facet].push(t)
    }
    this.facetGroups = Object.entries(grouped).map(([facet, tags]) => ({
      facet,
      label: FACET_LABELS[facet] || facet,
      tags
    }))
  }

  filteredFacetGroups(): FacetGroup[] {
    if (!this.tagSearch.trim()) return this.facetGroups
    const q = this.tagSearch.toLowerCase()
    return this.facetGroups
      .map(g => ({ ...g, tags: g.tags.filter(t => t.tag.toLowerCase().includes(q)) }))
      .filter(g => g.tags.length > 0)
  }

  setScene(value: string)          { this.sceneType    = value }
  setPeople(value: number | null)  { this.peopleMin    = value }
  setDuplicates(value: boolean)    { this.noDuplicates = value }
  setDate(from: string, to: string){ this.dateFrom = from; this.dateTo = to }

  isDateActive(from: string, to: string) {
    return this.dateFrom === from && this.dateTo === to
  }

  onQualityChange(event: Event) {
    this.qualityMin = Number((event.target as HTMLInputElement).value) / 100
  }

  isTagSelected(tag: string) { return this.selectedTags.includes(tag) }

  toggleTag(tag: string) {
    this.selectedTags = this.isTagSelected(tag)
      ? this.selectedTags.filter(t => t !== tag)
      : [...this.selectedTags, tag]
  }

  onApply() {
    this.apply.emit({
      scene_type:    this.sceneType,
      people_min:    this.peopleMin,
      quality_min:   this.qualityMin,
      date_from:     this.dateFrom,
      date_to:       this.dateTo,
      no_duplicates: this.noDuplicates,
      tags:          this.selectedTags,
      category:      '',
      sort:          this.filters?.sort  || 'overall_score',
      order:         this.filters?.order || 'DESC',
      page:          1,
      limit:         this.filters?.limit || 24,
    })
  }

  onClear() { this.clear.emit() }
}