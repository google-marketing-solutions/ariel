/**
 * @jest-environment jsdom
 */

import { checkOverlap, showToast } from './utils';

describe('Utils', () => {
  describe('showToast', () => {
    beforeEach(() => {
      document.body.innerHTML = '<div id="toast-container"></div>';
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
      document.body.innerHTML = '';
    });

    it('should create and append a toast element', () => {
      showToast('Test Message', 'success');
      const toast = document.querySelector('.toast');
      expect(toast).toBeTruthy();
      expect(toast.textContent).toBe('Test Message');
      expect(toast.classList.contains('success')).toBe(true);
    });

    it('should remove toast after duration', () => {
      showToast('Test Message', 'success', 1000);
      const toast = document.querySelector('.toast');

      // Fast-forward time
      jest.advanceTimersByTime(100); // Animation start
      expect(toast.classList.contains('show')).toBe(true);

      jest.advanceTimersByTime(1000); // Duration
      expect(toast.classList.contains('show')).toBe(false);

      jest.advanceTimersByTime(500); // Transition
      expect(document.querySelector('.toast')).toBeNull();
    });
  });

  describe('checkOverlap', () => {
    it('should detect overlaps', () => {
      const u1 = {id: '1', translated_start_time: 0, translated_end_time: 10};
      const u2 = {id: '2', translated_start_time: 5, translated_end_time: 15};

      const messages = checkOverlap(u2, [u1, u2]);
      expect(messages.length).toBeGreaterThan(0);
      expect(messages[0]).toContain('overlaps');
    });

    it('should ignore self and removed utterances', () => {
      const u1 = {id: '1', translated_start_time: 0, translated_end_time: 10};
      const u2 = {id: '2', translated_start_time: 0, translated_end_time: 10, removed: true};

      const messages = checkOverlap(u1, [u1, u2]);
      expect(messages.length).toBe(0);
    });
  });
});
