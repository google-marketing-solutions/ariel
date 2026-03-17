import { Component, inject, signal, ChangeDetectionStrategy } from '@angular/core';
import { Router } from '@angular/router';

export interface ResultData {
  video_url?: string;
  merged_audio_url?: string;
  vocals_url?: string;
  video_id?: string;
}

@Component({
  selector: 'app-result',
  imports: [],
  templateUrl: './result.html',
  styleUrl: './result.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class Result {
  private router = inject(Router);
  finalVideoData = signal<ResultData | null>(null);
  originalVideoData = signal<ResultData | null>(null);

  constructor() {
    const navigation = this.router.getCurrentNavigation();
    const state = navigation?.extras.state as { finalVideoData: ResultData, originalVideoData: ResultData } | undefined;
    if (state) {
      this.finalVideoData.set(state.finalVideoData);
      this.originalVideoData.set(state.originalVideoData);
    } else {
      this.finalVideoData.set(history.state.finalVideoData);
      this.originalVideoData.set(history.state.originalVideoData);
    }

    // Redirect if direct access without data
    if (!this.finalVideoData()) {
      this.router.navigate(['/']);
    }
  }

  goBack() {
    const original = this.originalVideoData() as { video_id?: string } | null;
    this.router.navigate(['/editor'], { queryParams: { video_id: original?.video_id } });
  }

  startOver() {
    this.router.navigate(['/']);
  }
}
