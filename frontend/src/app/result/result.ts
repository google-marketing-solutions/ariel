import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from '@angular/core';
import {Router} from '@angular/router';

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
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Result {
  private router = inject(Router);
  finalVideoData = signal<ResultData | null>(null);
  originalVideoData = signal<ResultData | null>(null);

  constructor() {
    const navigation = this.router.getCurrentNavigation();
    const state = navigation?.extras.state as
      | {finalVideoData: ResultData; originalVideoData: ResultData}
      | undefined;
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
    const original = this.originalVideoData() as {video_id?: string} | null;
    this.router.navigate(['/editor'], {
      queryParams: {video_id: original?.video_id},
    });
  }

  startOver() {
    this.router.navigate(['/']);
  }

  getCleanVideoName(): string {
    const data = this.originalVideoData() as any;
    if (!data || !data.video_id) return 'video.mp4';
    const cleanId = data.video_id.replace(
      /^.+?-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-/i,
      '',
    );
    const lang = data.translate_language;
    return lang ? `${cleanId}.${lang}.mp4` : cleanId;
  }

  getCleanAudioName(type: 'audio' | 'vocals'): string {
    const data = this.originalVideoData() as any;
    if (!data || !data.video_id) return `${type}.wav`;
    let cleanId = data.video_id.replace(
      /^.+?-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-/i,
      '',
    );
    cleanId = cleanId.replace(/\.mp4$/i, '');
    const lang = data.translate_language;
    return lang ? `${cleanId}_${type}.${lang}.wav` : `${cleanId}_${type}.wav`;
  }
}
