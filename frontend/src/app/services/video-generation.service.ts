import {Injectable, signal} from '@angular/core';
import {Subject} from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class VideoGenerationService {
  private generateVideoSource = new Subject<void>();
  private privateUnregeneratedCount = signal(0);
  private privateIsProcessingAudio = signal(false);

  // Observable string streams
  generateVideo$ = this.generateVideoSource.asObservable();
  unregeneratedCount = this.privateUnregeneratedCount.asReadonly();
  isProcessingAudio = this.privateIsProcessingAudio.asReadonly();

  // Service message commands
  triggerGenerateVideo() {
    this.generateVideoSource.next();
  }

  updateUnregeneratedCount(count: number) {
    this.privateUnregeneratedCount.set(count);
  }

  setProcessingAudio(isProcessing: boolean) {
    this.privateIsProcessingAudio.set(isProcessing);
  }
}
