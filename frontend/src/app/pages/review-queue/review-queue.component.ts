import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'
import { Observable } from 'rxjs'
import { ReviewService } from '../../services/review.service'
import { environment } from '../../../../environments/environment'
import {
  QueueImage, QueueResponse,
  DuplicateCluster, ClusterMember
} from '../../models'

@Component({
  selector: 'app-review-queue',
  templateUrl: './review-queue.component.html',
  styleUrls: ['./review-queue.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule]
})
export class ReviewQueueComponent implements OnInit {

  // ── Tab ──────────────────────────────────────────
  activeTab: 'tags' | 'duplicates' = 'tags'

  // ── Tag review state ─────────────────────────────
  queueImages:     QueueImage[] = []
  queueTotal:      number       = 0
  queueLoading:    boolean      = true
  currentIndex:    number       = 0
  reviewer:        string       = 'staff'

  // Queue pagination
  queuePage:       number       = 1
  queueLimit:      number       = 10
  queuePages:      number       = 0

  editScene:       string       = ''
  editPeople:      number       = 0
  editTags:        string[]     = []
  newTagInput:     string       = ''

  // ── Duplicate review state ───────────────────────
  clusters:        DuplicateCluster[] = []
  clustersTotal:   number             = 0
  clustersLoading: boolean            = true
  clustersPage:    number             = 1

  constructor(private reviewService: ReviewService) {}

  ngOnInit() {
    this.loadQueue()
    this.loadClusters()
  }

  // ── Tab ───────────────────────────────────────────

  setTab(tab: 'tags' | 'duplicates') {
    this.activeTab = tab
  }

  // ── Shared image error handler ────────────────────
  // Used in template instead of inline $event.target.style — avoids TS strict error
  onImgError(event: Event) {
    const img = event.target as HTMLImageElement
    img.style.display = 'none'
  }

  // ── Tag review ────────────────────────────────────

  loadQueue() {
    this.queueLoading = true
    this.reviewService.getQueue(this.queuePage, this.queueLimit).subscribe({
      next: (res: QueueResponse) => {
        this.queueImages  = res.images
        this.queueTotal   = res.total
        this.queuePages   = Math.ceil(res.total / this.queueLimit)
        this.queueLoading = false
        if (res.images.length > 0) {
          this.selectImage(0)
        }
      },
      error: () => { this.queueLoading = false }
    })
  }

  queuePrevPage() {
    if (this.queuePage > 1) {
      this.queuePage--
      this.loadQueue()
    }
  }

  queueNextPage() {
    if (this.queuePage < this.queuePages) {
      this.queuePage++
      this.loadQueue()
    }
  }

  get currentImage(): QueueImage | null {
    return this.queueImages[this.currentIndex] ?? null
  }

  selectImage(index: number) {
    this.currentIndex = index
    const img = this.queueImages[index]
    if (!img) return
    this.editScene   = img.scene_type   ?? ''
    this.editPeople  = img.people_count ?? 0
    this.editTags    = img.tags ? img.tags.map(t => t.tag) : []
    this.newTagInput = ''
  }

  getImageUrl(image: QueueImage): string {
    return `${environment.apiUrl}/images/${image.id}/file`
  }

  isLowConfidence(conf: number | null): boolean {
    return conf !== null && conf < 0.55
  }

  isMedConfidence(conf: number | null): boolean {
    return conf !== null && conf >= 0.55 && conf < 0.70
  }

  removeTag(tag: string) {
    this.editTags = this.editTags.filter(t => t !== tag)
  }

  addTag() {
    const tag = this.newTagInput.trim().toLowerCase()
    if (tag && !this.editTags.includes(tag)) {
      this.editTags = [...this.editTags, tag]
    }
    this.newTagInput = ''
  }

  onTagInputKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      this.addTag()
    }
  }

  confirmTags() {
    if (!this.currentImage) return
    this.reviewService.confirmTags(this.currentImage.id, this.reviewer).subscribe({
      next: () => this.removeCurrentAndAdvance()
    })
  }

  saveCorrections() {
    if (!this.currentImage) return
    const img   = this.currentImage
    const saves: Observable<any>[] = []

    if (this.editScene !== img.scene_type) {
      saves.push(this.reviewService.saveCorrection(
        img.id, 'scene_type',
        img.scene_type ?? '', this.editScene,
        this.reviewer
      ))
    }

    if (this.editPeople !== img.people_count) {
      saves.push(this.reviewService.saveCorrection(
        img.id, 'people_count',
        String(img.people_count ?? ''), String(this.editPeople),
        this.reviewer
      ))
    }

    const originalTags = img.tags ? img.tags.map(t => t.tag).sort().join(',') : ''
    const editedTags   = [...this.editTags].sort().join(',')
    if (editedTags !== originalTags) {
      saves.push(this.reviewService.saveCorrection(
        img.id, 'tags',
        originalTags, editedTags,
        this.reviewer
      ))
    }

    if (saves.length === 0) {
      this.confirmTags()
      return
    }

    let completed = 0
    saves.forEach(obs => {
      obs.subscribe({
        next: () => {
          completed++
          if (completed === saves.length) {
            this.removeCurrentAndAdvance()
          }
        }
      })
    })
  }

  skip() {
    this.advance()
  }

  private removeCurrentAndAdvance() {
    this.queueImages.splice(this.currentIndex, 1)
    this.queueTotal--
    if (this.currentIndex >= this.queueImages.length) {
      this.currentIndex = Math.max(0, this.queueImages.length - 1)
    }
    if (this.queueImages.length > 0) {
      this.selectImage(this.currentIndex)
    }
  }

  private advance() {
    if (this.currentIndex < this.queueImages.length - 1) {
      this.selectImage(this.currentIndex + 1)
    }
  }

  prev() {
    if (this.currentIndex > 0) {
      this.selectImage(this.currentIndex - 1)
    }
  }

  next() {
    if (this.currentIndex < this.queueImages.length - 1) {
      this.selectImage(this.currentIndex + 1)
    }
  }

  // ── Duplicate review ──────────────────────────────

  loadClusters() {
    this.clustersLoading = true
    this.reviewService.getClusters(this.clustersPage, 10).subscribe({
      next: (res) => {
        this.clusters        = res.clusters
        this.clustersTotal   = res.total
        this.clustersLoading = false
      },
      error: () => { this.clustersLoading = false }
    })
  }

  setRepresentative(cluster: DuplicateCluster, member: ClusterMember) {
    this.reviewService.setRepresentative(cluster.cluster_id, member.id).subscribe({
      next: () => {
        cluster.members.forEach(m => m.is_representative = false)
        member.is_representative  = true
        cluster.representative_id = member.id
      }
    })
  }

  removeFromCluster(cluster: DuplicateCluster, member: ClusterMember) {
    this.reviewService.removeFromCluster(
      cluster.cluster_id,
      member.id,
      member.is_representative
    ).subscribe({
      next: (res) => {
        if (res.dissolved) {
          this.clusters      = this.clusters.filter(c => c.cluster_id !== cluster.cluster_id)
          this.clustersTotal--
        } else {
          cluster.members      = cluster.members.filter(m => m.id !== member.id)
          cluster.member_count--
          if (member.is_representative && res.new_representative) {
            const newRep = cluster.members.find(m => m.id === res.new_representative)
            if (newRep) {
              cluster.members.forEach(m => m.is_representative = false)
              newRep.is_representative  = true
              cluster.representative_id = newRep.id
            }
          }
        }
      }
    })
  }

  dissolveCluster(cluster: DuplicateCluster) {
    this.reviewService.dissolveCluster(cluster.cluster_id).subscribe({
      next: () => {
        this.clusters      = this.clusters.filter(c => c.cluster_id !== cluster.cluster_id)
        this.clustersTotal--
      }
    })
  }

  getClusterImageUrl(member: ClusterMember): string {
    return `${environment.apiUrl}/images/${member.id}/file`
  }
}