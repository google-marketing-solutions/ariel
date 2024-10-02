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
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  FormsModule,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSliderModule } from '@angular/material/slider';
import { MatStepperModule } from '@angular/material/stepper';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Chip, InputChipsComponent } from './input-chips.component';

interface Dubbing {
  text: string;
  translated_text: string;
  editing: boolean;
  // TODO(ehsaanqadir@): Add additional fields like timing etc.
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatCardModule,
    MatInputModule,
    MatFormFieldModule,
    FormsModule,
    MatCheckboxModule,
    MatTooltipModule,
    MatSliderModule,
    InputChipsComponent,
    MatExpansionModule,
    HttpClientModule,
    MatStepperModule,
    ReactiveFormsModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  title = 'Ariel UI';
  preferredVoices: Chip[] = [
    { name: 'Journey' },
    { name: 'Studio' },
    { name: 'Wavenet' },
    { name: 'Polyglot' },
    { name: 'News' },
    { name: 'neural2' },
    { name: 'Standard' },
  ];
  loadingTranslations = false;
  dubbingCompleted = false;

  readonly configPanelOpenState = signal(true);
  readonly videoSettingsPanelOpenState = signal(true);
  dubbedInstances: any;
  dubbedUrl: string = '/assets/sample_dub.json';

  constructor(private http: HttpClient) {}

  async generateTranslations() {
    // TODO(): Call the cloud run backend to generate the translations and return them.
    this.loadingTranslations = true;
    await new Promise(r => setTimeout(r, 2000)); // TODO(): Get rid of me.
    this.http.get(this.dubbedUrl).subscribe(res => {
      this.dubbedInstances = res;
      this.loadingTranslations = false;
    });
  }
  toggleEdit(dubbing: any): void {
    dubbing.editing = !dubbing.editing;
  }

  async dubVideo() {
    await new Promise(r => setTimeout(r, 2000)); // TODO(): Get rid of me.
    this.dubbingCompleted = true;
  }

  private _formBuilder = inject(FormBuilder);

  firstFormGroup = this._formBuilder.group({
    firstCtrl: ['', Validators.required],
  });
  secondFormGroup = this._formBuilder.group({
    secondCtrl: ['', Validators.required],
  });
  isLinear = false;
}
