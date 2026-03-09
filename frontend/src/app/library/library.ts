import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

interface VideoJob {
  id: string;
  filename: string;
  dateCreated: string;
  sourceLanguage: string;
  targetLanguage: string;
  thumbnailUrl: string;
  progress: number;
  duration: string;
  status: 'processing' | 'completed' | 'failed';
}

@Component({
  selector: 'app-library',
  imports: [RouterLink],
  templateUrl: './library.html',
  styleUrl: './library.scss'
})
export class Library {

  videos: VideoJob[] = [
    {
      id: '1',
      filename: 'grant.mp4.pl-PL.mp4',
      dateCreated: '3/3/2026, 11:27:45 AM',
      sourceLanguage: 'en-US',
      targetLanguage: 'pl-PL',
      thumbnailUrl: 'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=800&q=80',
      progress: 33,
      duration: '0:00',
      status: 'processing'
    },
    {
      id: '2',
      filename: 'grant.mp4.it-IT.mp4',
      dateCreated: '2/27/2026, 2:53:49 PM',
      sourceLanguage: 'en-US',
      targetLanguage: 'it-IT',
      thumbnailUrl: 'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=800&q=80',
      progress: 0,
      duration: '0:00',
      status: 'processing'
    },
    {
      id: '3',
      filename: 'grant.mp4.pt-BR.mp4',
      dateCreated: '2/16/2026, 1:49:52 PM',
      sourceLanguage: 'en-US',
      targetLanguage: 'pt-BR',
      thumbnailUrl: 'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=800&q=80',
      progress: 40,
      duration: '0:00',
      status: 'processing'
    },
    {
      id: '4',
      filename: 'grant.mp4.de-DE.mp4',
      dateCreated: '2/16/2026, 1:29:19 PM',
      sourceLanguage: 'en-US',
      targetLanguage: 'de-DE',
      thumbnailUrl: 'https://images.unsplash.com/photo-1542744173-8e7e53415bb0?auto=format&fit=crop&w=800&q=80',
      progress: 20,
      duration: '0:00',
      status: 'processing'
    }
  ];

}
