import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-result',
  imports: [],
  templateUrl: './result.html',
  styleUrl: './result.scss',
})
export class Result {
  private router = inject(Router);
  finalVideoData: any;
  originalVideoData: any;

  constructor() {
    const navigation = this.router.getCurrentNavigation();
    const state = navigation?.extras.state as { finalVideoData: any, originalVideoData: any };
    if (state) {
      this.finalVideoData = state.finalVideoData;
      this.originalVideoData = state.originalVideoData;
    } else {
      this.finalVideoData = history.state.finalVideoData;
      this.originalVideoData = history.state.originalVideoData;
    }

    // Redirect if direct access without data
    if (!this.finalVideoData) {
      this.router.navigate(['/']);
    }
  }

  goBack() {
    this.router.navigate(['/editor'], { queryParams: { video_id: this.originalVideoData?.video_id } });
  }

  startOver() {
    this.router.navigate(['/']);
  }
}
