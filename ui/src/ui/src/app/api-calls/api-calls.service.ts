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
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, NgZone } from '@angular/core';
import {
  catchError,
  filter,
  firstValueFrom,
  map,
  Observable,
  of,
  retry,
  switchMap,
  take,
  takeWhile,
  throwError,
  timer,
} from 'rxjs';
import { CONFIG } from '../../../../config';
import { ApiCalls } from './api-calls.service.interface';

/**
 * This class provides methods to call our cloud backend.
 * It uses authentication tokens from Google Apps Script to provide a seamless
 * experience for calling Google Cloud endpoints without additional auth setup.
 */
@Injectable({
  providedIn: 'root',
})
export class ApiCallsService implements ApiCalls {
  constructor(
    private ngZone: NgZone,
    private httpClient: HttpClient
  ) {}

  getUserAuthToken(): Observable<string> {
    return new Observable<string>(subscriber => {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      google.script.run
        .withSuccessHandler((userAuthToken: string) => {
          this.ngZone.run(() => {
            subscriber.next(userAuthToken);
            subscriber.complete();
          });
        })
        .getUserAuthToken();
    });
  }

  postToGcs(
    file: File,
    folder: string,
    filename: string,
    contentType?: string
  ): Observable<string[]> {
    // Determine the content type if not provided.
    if (!contentType) {
      if (file.type.startsWith('video/')) {
        contentType = file.type;
      } else if (file.type === 'application/json') {
        contentType = 'application/json';
      } else {
        throw new Error(
          `Unsupported file type: ${file.type}. Only video and JSON files are allowed.`
        );
      }
    }

    const fullName = encodeURIComponent(`${folder}/${filename}`);
    const url = `${CONFIG.cloudStorage.uploadEndpointBase}/b/${CONFIG.cloudStorage.bucket}/o?uploadType=media&name=${fullName}`;

    if (CONFIG.debug) {
      console.log(`Fullname: ${fullName}\nURL: ${url}`);
    }

    return this.getUserAuthToken().pipe(
      switchMap(userAuthToken =>
        this.httpClient
          .post(url, file, {
            headers: new HttpHeaders({
              'Authorization': `Bearer ${userAuthToken}`,
              'Content-Type': contentType,
            }),
          })
          .pipe(
            switchMap(response => {
              console.log('Upload complete!', response);
              const filePath = `${CONFIG.cloudStorage.authenticatedEndpointBase}/${CONFIG.cloudStorage.bucket}/${encodeURIComponent(folder)}/${filename}`;
              return of([folder, filePath]);
            })
          )
      )
    );
  }

  getFromGcs(url: string, retryDelay = 0, maxRetries = 0): Observable<string> {
    const gcsUrl = `${CONFIG.cloudStorage.endpointBase}/b/${CONFIG.cloudStorage.bucket}/o/${encodeURIComponent(url)}?alt=media`;

    return this.getUserAuthToken().pipe(
      switchMap(userAuthToken =>
        this.httpClient.get(gcsUrl, {
          responseType: 'text',
          headers: new HttpHeaders({
            Authorization: `Bearer ${userAuthToken}`,
          }),
        })
      ),
      retry({
        count: maxRetries,
        delay: (error, retryCount) => {
          if (
            (error.status && error.status !== 404) ||
            retryCount >= maxRetries
          ) {
            throw new Error(`Received an unexpected error: ${error.message}`);
          }
          return timer(retryDelay);
        },
      })
    );
  }

  async getErrorLog(
    url: string,
    retryDelay = 0,
    maxRetries = 0
  ): Promise<string> {
    try {
      const errorLog = await firstValueFrom(
        this.getFromGcs(url, retryDelay, maxRetries)
      );
      return errorLog;
    } catch (error) {
      console.error('Unable to fetch error log:', error);
      return 'An unexpected error occurred. Please try again later.';
    }
  }

  checkGcsFileDeletion(
    url: string,
    retryDelay = 0,
    maxRetries = 0
  ): Observable<boolean> {
    const gcsUrl = `${CONFIG.cloudStorage.endpointBase}/b/${CONFIG.cloudStorage.bucket}/o/${encodeURIComponent(url)}`;

    return this.getUserAuthToken().pipe(
      // Take only the first value.
      take(1),
      switchMap(authToken => {
        let retries = 0; // Count the number of retries.

        // Create an interval observable.
        return timer(0, retryDelay).pipe(
          // Use takeWhile to repeat until the max retries are reached or file is deleted.
          takeWhile(() => retries < maxRetries),
          // Try fetching the file from GCS.
          switchMap(() =>
            this.httpClient
              .get(gcsUrl, {
                headers: { Authorization: `Bearer ${authToken}` },
              })
              .pipe(
                map(() => {
                  retries++;
                  return false; // If file exists, return false (not deleted).
                }),
                catchError(error => {
                  if (error.status === 404) {
                    // If file is deleted (404), stop retries.
                    return of(true); // Return true indicating the file was deleted.
                  }
                  // For other errors, rethrow.
                  throw error;
                })
              )
          ),
          // Retry until the file is deleted or max retries reached.
          catchError(error => {
            if (retries >= maxRetries) {
              // If maxRetries reached and file is not deleted, return false.
              return of(false);
            }
            return throwError(() => new Error(error)); // Propagate other errors.
          })
        );
      }),
      // Only emit when the check returns true (file deleted).
      filter(deleted => deleted),
      // Only emit the first result (when file is deleted).
      take(1)
    );
  }

  downloadBlob(url: string, retryDelay = 0, maxRetries = 0): Observable<Blob> {
    const gcsUrl = `${CONFIG.cloudStorage.endpointBase}/b/${CONFIG.cloudStorage.bucket}/o/${encodeURIComponent(url)}?alt=media`;

    return this.getUserAuthToken().pipe(
      switchMap(userAuthToken =>
        this.httpClient.get(gcsUrl, {
          responseType: 'blob',
          headers: new HttpHeaders({
            Authorization: `Bearer ${userAuthToken}`,
          }),
        })
      ),
      retry({
        count: maxRetries,
        delay: (error, retryCount) => {
          if (
            (error.status && error.status !== 404) ||
            retryCount >= maxRetries
          ) {
            throw new Error(`Received an unexpected error: ${error}`);
          }
          return timer(retryDelay);
        },
      })
    );
  }
}
