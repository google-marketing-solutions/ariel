/**
 * @jest-environment jsdom
 */

import { renderTimeline } from './timeline';
import { checkOverlap } from './utils';

// Mock dependencies
jest.mock('./utils', () => ({
  checkOverlap: jest.fn().mockReturnValue([]),
}));

jest.mock('./utterance', () => ({
  editUtterance: jest.fn(),
}));

describe('Timeline', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="timeline" style="width: 1150px;"></div>
      <div id="timeline-markers"></div>
      <div id="original-speaker-labels"></div>
      <div id="original-utterances-tracks"></div>
      <div id="translated-speaker-labels"></div>
      <div id="translated-utterances-tracks"></div>
      <div id="utterance-editor"></div>
      <div id="translated-overlap-warning"></div>
    `;

    // Reset mocks
    checkOverlap.mockClear();
  });

  it('should render timeline correctly', () => {
    const videoData = {
      utterances: [
        {
            id: 'u1',
            original_start_time: 0,
            original_end_time: 5,
            translated_start_time: 0,
            translated_end_time: 5,
            speaker: {voice: 'Voice1'},
            muted: false,
            removed: false
        }
      ]
    };
    const speakers = [{voice: 'Voice1', name: 'Speaker 1'}];
    const videoDuration = 10;

    renderTimeline(videoData, videoDuration, speakers);

    // Check if tracks are created
    expect(document.getElementById('original-speaker-track-Voice1')).toBeTruthy();
    expect(document.getElementById('translated-speaker-track-Voice1')).toBeTruthy();

    // Check if utterance blocks are created
    const originalTrack = document.getElementById('original-speaker-track-Voice1');
    const translatedTrack = document.getElementById('translated-speaker-track-Voice1');

    expect(originalTrack.children.length).toBe(1);
    expect(translatedTrack.children.length).toBe(1);

    const translatedBlock = translatedTrack.children[0];
    expect(translatedBlock.textContent).toContain('U: 1');
  });

  it('should mark overlap', () => {
    checkOverlap.mockReturnValue(['Overlap detected']);
    const videoData = {
      utterances: [
        {
            id: 'u1',
            original_start_time: 0,
            original_end_time: 5,
            translated_start_time: 0,
            translated_end_time: 5,
            speaker: {voice: 'Voice1'},
            muted: false,
            removed: false
        }
      ]
    };

    renderTimeline(videoData, 10, [{voice: 'Voice1', name: 'Speaker 1'}]);

    const translatedTrack = document.getElementById('translated-speaker-track-Voice1');
    const translatedBlock = translatedTrack.children[0];
    expect(translatedBlock.classList.contains('overlap')).toBe(true);
  });
});
