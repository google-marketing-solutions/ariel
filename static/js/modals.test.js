/**
 * @jest-environment jsdom
 */

import { addVoice, renderVoiceList } from './modals';
import { showToast } from './utils';

// Mock utils
jest.mock('./utils', () => ({
  showToast: jest.fn(),
}));

// Mock state
jest.mock('./state', () => ({
  appState: {
    editingSpeakerId: null,
    isEditingVideoSettings: false,
  },
}));

describe('Modals', () => {
  beforeEach(() => {
    // Reset DOM
    document.body.innerHTML = '';

    // Mock bootstrap
    window.bootstrap = {
      Modal: jest.fn().mockImplementation(() => ({
        hide: jest.fn(),
        show: jest.fn(),
      })),
      Modal: {
        getInstance: jest.fn().mockImplementation(() => ({
          hide: jest.fn(),
        })),
      }
    };

    // Mock Audio
    global.Audio = jest.fn().mockImplementation(() => ({
      play: jest.fn(),
      pause: jest.fn(),
      addEventListener: jest.fn(),
    }));
  });

  describe('renderVoiceList', () => {
    let targetList;
    let searchInput;

    beforeEach(() => {
      targetList = document.createElement('div');
      searchInput = document.createElement('input');
      searchInput.value = '';

      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'gender-filter';
      radio.value = 'all';
      radio.checked = true;
      document.body.appendChild(radio);
    });

    it('should render voices that match search and filter', () => {
      const voices = [
        {name: 'Voice1', gender: 'Male', url: 'url1'},
        {name: 'Voice2', gender: 'Female', url: 'url2'},
      ];

      renderVoiceList(targetList, searchInput, 'gender-filter', voices, jest.fn(), 'Voice1');

      expect(targetList.children.length).toBe(2);
      expect(targetList.children[0].classList.contains('active')).toBe(true);
      expect(targetList.children[1].classList.contains('active')).toBe(false);
    });

    it('should filter by name', () => {
      const voices = [
        {name: 'Alpha', gender: 'Male'},
        {name: 'Beta', gender: 'Female'},
      ];
      searchInput.value = 'alpha';

      renderVoiceList(targetList, searchInput, 'gender-filter', voices, jest.fn(), '');

      expect(targetList.children.length).toBe(1);
      expect(targetList.textContent).toContain('Alpha');
    });
  });

  describe('addVoice', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="speaker-modal"></div>
        <input id="speaker-name-input" value="Custom Name" />
      `;
    });

    it('should add a new speaker', () => {
      const speakers = [];
      const renderSpeakers = jest.fn();
      const validate = jest.fn();
      const voiceData = {name: 'Voice1', gender: 'Male'};

      addVoice(voiceData, speakers, renderSpeakers, validate);

      expect(speakers.length).toBe(1);
      expect(speakers[0].name).toBe('Custom Name');
      expect(speakers[0].voice).toBe('Voice1');
      expect(renderSpeakers).toHaveBeenCalled();
      expect(validate).toHaveBeenCalled();
    });

    it('should show error if no voice data', () => {
      addVoice(null, [], jest.fn(), jest.fn());
      expect(showToast).toHaveBeenCalledWith(expect.stringContaining('not be found'), 'error');
    });
  });
});
