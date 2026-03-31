import {Injectable, signal} from '@angular/core';
import {Subject} from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class VideoGenerationService {
  private generateVideoSource = new Subject<void>();
  private _unregeneratedCount = signal(0);
  private _isProcessingAudio = signal(false);

  // Observable string streams
  generateVideo$ = this.generateVideoSource.asObservable();
  unregeneratedCount = this._unregeneratedCount.asReadonly();
  isProcessingAudio = this._isProcessingAudio.asReadonly();

  // Service message commands
  triggerGenerateVideo() {
    this.generateVideoSource.next();
  }

  updateUnregeneratedCount(count: number) {
    this._unregeneratedCount.set(count);
  }

  setProcessingAudio(isProcessing: boolean) {
    this._isProcessingAudio.set(isProcessing);
  }
}
