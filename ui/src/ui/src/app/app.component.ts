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
import { Component, inject, signal, WritableSignal } from '@angular/core';
import {
  FormArray,
  FormBuilder,
  FormsModule,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import {
  MatCheckboxChange,
  MatCheckboxModule,
} from '@angular/material/checkbox';
import { MatChipInputEvent, MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatStepperModule } from '@angular/material/stepper';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { switchMap, tap } from 'rxjs';
import { CONFIG } from '../../../config';
import { ApiCallsService } from './api-calls/api-calls.service';
import { ErrorDialogComponent } from './error-dialog/error-dialog.component';

interface Dubbing {
  start: number;
  end: number;
  path: string;
  text: string;
  for_dubbing: boolean;
  speaker_id: string;
  ssml_gender: string;
  dubbed_path: string;
  translated_text: string;
  assigned_voice: string;
  pitch: number;
  speed: number;
  volume_gain_db: number;
  adjust_speed: boolean;
  editing?: boolean;
  stability?: number;
  similarity_boost?: number;
  style?: number;
  use_speaker_boost?: boolean;
}
interface Voice {
  [voiceName: string]: string;
}

interface Speaker {
  [id: string]: {
    voice: string;
    gender: string;
  };
}

/**
 * This is the main UI component for Ariel.
 * It provides forms and various settings to generate a dubbed video ad.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatInputModule,
    MatFormFieldModule,
    FormsModule,
    MatCheckboxModule,
    MatTooltipModule,
    MatSliderModule,
    MatExpansionModule,
    MatStepperModule,
    ReactiveFormsModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  title = 'Ariel UI';
  readonly preferredVoices = signal([]);
  readonly noDubbingPhrases = signal([]);
  availableVoices: Voice = {};
  objectKeys = Object.keys;
  speakers: Speaker = {};
  loadingTranslations = false;
  loadingDubbedVideo = false;
  dubbingCompleted = false;
  selectedFile: File | null = null;
  selectedFileUrl = '';
  dubbedInstances!: Dubbing[];
  dubbedUrl = '';
  gcsFolder = '';
  editSpeakerList = false;

  constructor(
    private apiCalls: ApiCallsService,
    private dialog: MatDialog
  ) {}

  onFileSelected(event: Event) {
    const inputElement = event.target as HTMLInputElement;
    if (inputElement && inputElement.files && inputElement.files.length > 0) {
      this.selectedFile = inputElement.files[0];
      this.selectedFileUrl = URL.createObjectURL(this.selectedFile);
    } else {
      // Handle the case where the input element or files are null/undefined.
      console.error('No file selected or target is not an input element.');
    }
  }

  playAudio(url: string) {
    console.log(`Received request to play audio from ${url}`);
    // Remove /tmp paths from the url string.
    if (url.startsWith('/tmp/ariel/')) {
      url = url.replace('/tmp/ariel/', '');
      // Build gcs audio path and fetch file.
      this.apiCalls.downloadBlob(`${url}`, 0, 0).subscribe(response => {
        console.log('Audio snippet fetched!', response);
        const audioUrl = URL.createObjectURL(response as unknown as Blob);
        const audio = new Audio(audioUrl);
        audio.play();
      });
    }
  }

  showErrorDialog(message: string) {
    this.dialog.open(ErrorDialogComponent, {
      data: { message },
    });
  }

  toggleToDub(dubbing: Dubbing): void {
    dubbing.for_dubbing = !dubbing.for_dubbing;
  }

  // TODO(ehsaanqadir): Refactor the method, extracting logic into separate functions.
  saveDubbing(index: number) {
    // Update this.dubbedInstances based on changes from the form.
    const dubbings = this.translationsFormGroup.value['dubbings'];
    if (dubbings && dubbings[index]) {
      const newDubbingValues: Dubbing = dubbings[index];
      this.editSpeakerList = false; // Reset speaker edit view for the dubbing.
      for (const key in newDubbingValues) {
        if (
          key === 'editing' ||
          key === 'assigned_voice' ||
          key === 'ssml_gender' ||
          key === 'for_dubbing'
        ) {
          continue;
        } else if (key === 'speaker_id') {
          // Case: Existing speaker with gender and voice assigned from backend.
          if (newDubbingValues[key] in this.speakers) {
            this.dubbedInstances[index]['assigned_voice'] =
              this.speakers[newDubbingValues[key]].voice;
            this.dubbedInstances[index]['ssml_gender'] =
              this.speakers[newDubbingValues[key]].gender;
          } else {
            // Case: New speaker with user-assigned voice and its gender.
            //  Add new speaker to our speaker list.
            this.speakers[newDubbingValues[key]] = {
              voice: newDubbingValues['assigned_voice'],
              gender: this.availableVoices[newDubbingValues['assigned_voice']],
            };
            this.dubbedInstances[index]['assigned_voice'] =
              newDubbingValues['assigned_voice'];
            this.dubbedInstances[index]['ssml_gender'] =
              this.availableVoices[newDubbingValues['assigned_voice']];
          }
          this.dubbedInstances[index]['speaker_id'] = newDubbingValues[key];
        }
        // If adjust_speed is set to true, use the new speed value else ignore.
        else if (key === 'speed') {
          if (newDubbingValues['adjust_speed']) {
            this.dubbedInstances[index]['speed'] = newDubbingValues[key];
          }
        } else {
          this.dubbedInstances[index][key as keyof Dubbing] =
            dubbings[index][key];
        }
      }
      console.log(dubbings[index]);
      console.log(this.dubbedInstances[index]);
    }
    this.updateTranslations();
  }

  getCleanUtterances(utterances: Dubbing[]) {
    utterances.forEach(dubbing => {
      if (dubbing.editing) {
        delete dubbing.editing;
      }
    });
    return utterances;
  }

  updateTranslations() {
    this.loadingTranslations = true;
    // Upload new utterances_preview file.
    const cleanUtterances = this.getCleanUtterances(this.dubbedInstances);
    console.log(
      `Utterances preview generated and ready to be uploaded: ${cleanUtterances}`
    );
    this.apiCalls
      .postToGcs(
        this.jsonFile(
          JSON.stringify(cleanUtterances),
          'utterances_preview.json'
        ),
        this.gcsFolder,
        'utterances_preview.json'
      )
      .pipe(
        tap(response => {
          console.log('Utterances preview upload completed!', response);
        }),
        switchMap(() => {
          return this.apiCalls.checkGcsFileDeletion(
            `${this.gcsFolder}/utterances_preview.json`,
            15000,
            20
          );
        }),
        tap(response => {
          console.log('Utterances preview deleted!', response);
        }),
        switchMap(() => {
          return this.apiCalls.getFromGcs(
            `${this.gcsFolder}/utterances.json`,
            15000,
            4
          );
        })
      )
      .subscribe({
        next: response => {
          console.log('Updated utterances downloaded!', response);
          this.dubbedInstances = JSON.parse(response) as Dubbing[];
          this.translationsFormGroup = this._formBuilder.group({
            dubbings: new FormArray([]),
          });
          this.dubbedInstances.forEach(instance => {
            instance.editing = false;
            this.createDubbingObjectFormGroup(instance);
          });
          this.loadingTranslations = false;
        },
        error: async error => {
          this.loadingTranslations = false;
          console.error('Error in API call:', error);
          const errorLog = await this.apiCalls.getErrorLog(
            `${this.gcsFolder}/error.log`
          );
          this.showErrorDialog(errorLog);
        },
      });
  }

  toggleEdit(dubbing: Dubbing): void {
    dubbing.editing = !dubbing.editing;
  }

  toggleAdjustSpeed(dubbing: Dubbing): void {
    dubbing.adjust_speed = !dubbing.adjust_speed;
  }

  toggleSpeakerEdit(): void {
    this.editSpeakerList = !this.editSpeakerList;
  }

  toggleElevenLabs(event: MatCheckboxChange): void {
    const checked = event.checked;
    const token = this.configFormGroup.get('elevenlabs_token');
    if (checked) {
      token?.setValidators(Validators.required);
    } else {
      token?.clearValidators();
    }
    token?.updateValueAndValidity();
  }

  private _formBuilder = inject(FormBuilder);

  configFormGroup = this._formBuilder.group({
    input_video: ['', Validators.required],
    advertiser_name: ['', Validators.required],
    original_language: ['de-DE', Validators.required],
    target_language: ['pl-PL', Validators.required],
    hugging_face_token: ['', Validators.required],
    number_of_speakers: [1],
    no_dubbing_phrases: [this.noDubbingPhrases()],
    diarization_instructions: [''],
    translation_instructions: [''],
    merge_utterances: [true],
    minimum_merge_threshold: [0.001],
    preferred_voices: [this.preferredVoices()],
    assigned_voices_override: [''],
    keep_voice_assignments: [true],
    adjust_speed: [false],
    vocals_volume_adjustment: [5.0],
    background_volume_adjustment: [0.0],
    gemini_model_name: ['gemini-2.5-flash'],
    temperature: [1.0],
    top_p: [0.95],
    top_k: [40],
    max_output_tokens: [8192],
    safety_settings: ['Medium'],
    use_elevenlabs: [false],
    elevenlabs_token: [''],
    elevenlabs_clone_voices: [false],
    elevenlabs_remove_cloned_voices: [true],
  });
  translationsFormGroup = this._formBuilder.group({
    dubbings: new FormArray([]),
  });

  createDubbingObjectFormGroup(dubbing: Dubbing): void {
    const dubbingFormGroup = this._formBuilder.group({
      start: [dubbing.start, Validators.required],
      end: [dubbing.end, Validators.required],
      path: [dubbing.path, Validators.required],
      text: [dubbing.text, Validators.required],
      for_dubbing: [dubbing.for_dubbing, Validators.required],
      speaker_id: [dubbing.speaker_id, Validators.required],
      ssml_gender: [dubbing.ssml_gender, Validators.required],
      dubbed_path: [dubbing.dubbed_path, Validators.required],
      translated_text: [dubbing.translated_text, Validators.required],
      assigned_voice: [dubbing.assigned_voice, Validators.required],
      pitch: [dubbing.pitch],
      speed: [dubbing.speed, Validators.required],
      volume_gain_db: [dubbing.volume_gain_db],
      adjust_speed: [dubbing.adjust_speed, Validators.required],
      stability: [dubbing.stability],
      similarity_boost: [dubbing.similarity_boost],
      style: [dubbing.style],
      use_speaker_boost: [dubbing.use_speaker_boost],
      editing: [dubbing.editing],
    });
    (this.translationsFormGroup.get('dubbings') as FormArray).push(
      dubbingFormGroup
    );
  }

  get dubbingFormArray(): FormArray {
    return this.translationsFormGroup.get('dubbings') as FormArray;
  }

  removeChipEntry(chipsCollection: WritableSignal<string[]>, entry: string) {
    chipsCollection.update(chips => {
      const index = chips.indexOf(entry);
      if (index < 0) {
        return chips;
      }

      chips.splice(index, 1);
      return [...chips];
    });
  }

  addChipEntry(
    chipsCollection: WritableSignal<string[]>,
    event: MatChipInputEvent
  ): void {
    const value = (event.value || '').trim();
    if (value) {
      chipsCollection.update(chips => [...chips, value]);
    }
    // Clear the input value.
    event.chipInput!.clear();
  }

  dubVideo() {
    this.loadingDubbedVideo = true;
    this.dubbingCompleted = false;
    // Upload the (updated) utterances to gcs.
    this.apiCalls
      .postToGcs(
        this.jsonFile(
          JSON.stringify(this.dubbedInstances),
          'utterances_approved.json'
        ),
        this.gcsFolder,
        'utterances_approved.json'
      )
      .pipe(
        tap(response => {
          console.log('Approved utterances upload completed!', response);
        }),
        switchMap(() => {
          return this.apiCalls.downloadBlob(
            `${this.gcsFolder}/dubbed_video.mp4`,
            15000,
            8
          );
        })
      )
      .subscribe({
        next: response => {
          console.log('Dubbed video generated!', response);
          this.loadingDubbedVideo = false;
          this.dubbingCompleted = true;
          this.dubbedUrl = URL.createObjectURL(response as unknown as Blob);
        },
        error: async error => {
          this.loadingDubbedVideo = false;
          console.error('Error in API call:', error);
          const errorLog = await this.apiCalls.getErrorLog(
            `${this.gcsFolder}/error.log`
          );
          this.showErrorDialog(errorLog);
        },
      });
  }

  removeEmptyKeys(obj: object) {
    const result: { [key: string]: unknown } = {};
    for (const [key, value] of Object.entries(obj)) {
      if (key === 'input_video') {
        // Skip input_video as backend has own logic for it.
        continue;
      }
      if (value !== '' || value !== null || value !== undefined) {
        result[key] = value;
      }
    }
    return result;
  }

  jsonFile(jsonString: string, filename: string): File {
    return new File([jsonString], filename, {
      type: 'application/json',
    });
  }

  generateUtterances() {
    if (this.selectedFile && this.configFormGroup.valid) {
      this.loadingTranslations = true;
      const configData = this.configFormGroup.value;
      const configDataJson = JSON.stringify(this.removeEmptyKeys(configData));
      const configDataFile = this.jsonFile(configDataJson, 'config.json');
      console.log(
        `Requested dubbing for video ${this.selectedFile.name} with the following config: ${configDataJson}`
      );
      // 1. Upload video to gcs.
      this.gcsFolder = `${this.selectedFile.name}${CONFIG.videoFolderNameSeparator}${Date.now()}`;
      this.apiCalls
        .postToGcs(this.selectedFile!, this.gcsFolder, 'input.mp4')
        .pipe(
          tap(response => {
            console.log('Video upload completed!', response);
          }),
          switchMap(response => {
            const folder = response[0];
            return this.apiCalls.postToGcs(
              configDataFile,
              folder,
              'config.json'
            );
          }),
          tap(data => {
            console.log('Config upload completed!', data);
          }),
          switchMap(() => {
            return this.apiCalls.getFromGcs(
              `${this.gcsFolder}/utterances.json`,
              15000,
              20
            );
          }),
          tap(response => {
            console.log('Utterances generated!', response);
          }),
          switchMap(response => {
            this.dubbedInstances = JSON.parse(response) as Dubbing[];
            this.translationsFormGroup = this._formBuilder.group({
              dubbings: new FormArray([]),
            });
            this.dubbedInstances.forEach(instance => {
              this.createDubbingObjectFormGroup(instance);
            });
            const speakerSet = new Map(
              this.dubbedInstances.map(dubbing => [
                dubbing.speaker_id,
                {
                  gender: dubbing.ssml_gender,
                  voice: dubbing.assigned_voice,
                },
              ])
            );
            this.speakers = Object.fromEntries(speakerSet);
            return this.apiCalls.getFromGcs(
              `${this.gcsFolder}/voices.json`,
              15000,
              2
            );
          })
        )
        .subscribe({
          next: response => {
            const voiceJson = JSON.parse(response);
            this.availableVoices = { ...voiceJson };
            console.log(
              `Available voices: ${JSON.stringify(this.availableVoices)}`
            );
            this.loadingTranslations = false;
          },
          error: async error => {
            this.loadingTranslations = false;
            console.error('Error in API call:', error);
            const errorLog = await this.apiCalls.getErrorLog(
              `${this.gcsFolder}/error.log`
            );
            this.showErrorDialog(errorLog);
          },
        });
    } else {
      console.error('Invalid configuration form or no file selected.');
      // TODO(): Config form is invalid. Display error messages.
    }
  }
  isLinear = false;
}
