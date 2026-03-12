import { Injectable } from '@angular/core';
import { Subject, BehaviorSubject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class VideoGenerationService {
  private generateVideoSource = new Subject<void>();
  private unregeneratedCountSource = new BehaviorSubject<number>(0);

  // Observable string streams
  generateVideo$ = this.generateVideoSource.asObservable();
  unregeneratedCount$ = this.unregeneratedCountSource.asObservable();

  // Service message commands
  triggerGenerateVideo() {
    this.generateVideoSource.next();
  }

  updateUnregeneratedCount(count: number) {
    this.unregeneratedCountSource.next(count);
  }
}
