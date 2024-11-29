/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import { HttpClient } from '@angular/common/http';
import { Injectable, NgZone } from '@angular/core';
import { lastValueFrom, Observable, of } from 'rxjs';
import { ApiCalls } from './api-calls.service.interface';

/**
 * This class provides methods to mock calls to our backend.
 * It allows developers to test the UI locally without having to deploy code to
 * Google Apps Script.
 */
@Injectable({
  providedIn: 'root',
})
export class ApiCallsService implements ApiCalls {
  constructor(
    private ngZone: NgZone,
    private httpClient: HttpClient
  ) {}

  getFromGcs(data: string, retryDelay = 0, maxRetries = 0): Observable<string> {
    return new Observable(subscriber => {
      console.log(
        `Get from GCS called with the following config: ${data}, Retrydelay: ${retryDelay}, MaxRetries: ${maxRetries}`
      );
      let localFile: string;
      const filename = data.split('/').pop();
      switch (filename) {
        case 'utterances.json':
          localFile = '/assets/sample_utterances.json';
          break;
        case 'voices.json':
          localFile = '/assets/sample_voices.json';
          break;
        default:
          localFile = '/assets/sample_utterances.json';
      }

      setTimeout(() => {
        this.ngZone.run(async () => {
          subscriber.next(await this.loadLocalJsonFile(localFile));
          subscriber.complete();
        });
      }, 2000);
    });
  }

  checkGcsFileDeletion(
    url: string,
    retryDelay = 0,
    maxRetries = 0
  ): Observable<boolean> {
    return new Observable(subscriber => {
      console.log(
        `Checking for file existence: ${url}, Retrydelay: ${retryDelay}, MaxRetries: ${maxRetries}`
      );
      setTimeout(() => {
        this.ngZone.run(async () => {
          subscriber.next(true);
          subscriber.complete();
        });
      }, 2000);
    });
  }

  downloadBlob(data: string, retryDelay = 0, maxRetries = 0): Observable<Blob> {
    return new Observable(subscriber => {
      console.log(
        `Fake downloading blob with the following settings: ${data}, Retrydelay: ${retryDelay}, MaxRetries: ${maxRetries}`
      );
      setTimeout(() => {
        this.ngZone.run(async () => {
          const localFile = data.endsWith('.mp4')
            ? '/assets/sample_video.mp4'
            : '/assets/sample_audio_chunk.mp3';

          console.log(`Fetching local file: ${localFile}`);

          subscriber.next(await this.loadLocalBlob(localFile));
          subscriber.complete();
        });
      }, 2000);
    });
  }

  postToGcs(
    file: File,
    folder: string,
    filename: string,
    contentType: string
  ): Observable<string[]> {
    console.log(
      `Running locally. Fake file uploaded: ${file.name} with contentType ${contentType} `
    );
    return of([folder, filename]);
  }

  async loadLocalJsonFile(path: string) {
    const data = await lastValueFrom(
      this.httpClient.get(path, { responseType: 'text' })
    );
    return data;
  }

  async loadLocalBlob(path: string) {
    const data = await lastValueFrom(
      this.httpClient.get(path, { responseType: 'blob' })
    );
    return data;
  }

  async getErrorLog(
    url = 'error.log',
    retryDelay = 0,
    maxRetries = 0
  ): Promise<string> {
    return `Called ${url} with ${maxRetries} retries and ${retryDelay} delays:
    Reason: An unexpected error occurred. Please try again later.`;
  }
}
