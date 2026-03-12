import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class VideoGenerationService {
  private generateVideoSource = new Subject<void>();

  // Observable string streams
  generateVideo$ = this.generateVideoSource.asObservable();

  // Service message commands
  triggerGenerateVideo() {
    this.generateVideoSource.next();
  }
}
