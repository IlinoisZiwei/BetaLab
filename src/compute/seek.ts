/** Seek on every click, including the same timestamp twice. Wait for metadata first. */
export async function seekToMoment(video: HTMLVideoElement, seconds: number, lastFrameSeconds: number, signal?: AbortSignal): Promise<number> {
  if (!Number.isFinite(seconds) || !Number.isFinite(lastFrameSeconds) || lastFrameSeconds < 0)
    throw new Error("This time point isn't valid.");
  if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  if (video.readyState < 1) {
    await new Promise<void>((resolve, reject) => {
      const done = (error?: Error) => {
        clearTimeout(timer);
        video.removeEventListener('loadedmetadata', loaded);
        video.removeEventListener('error', failed);
        signal?.removeEventListener('abort', aborted);
        error ? reject(error) : resolve();
      };
      const loaded = () => done();
      const failed = () => done(new Error('The video could not load. Reopen the result and try again.'));
      const aborted = () => done(new DOMException('Cancelled', 'AbortError'));
      const timer = setTimeout(() => done(new Error('The video took too long to load. Please try again.')), 10000);
      video.addEventListener('loadedmetadata', loaded, { once: true });
      video.addEventListener('error', failed, { once: true });
      signal?.addEventListener('abort', aborted, { once: true });
      video.load();
    });
  }
  if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  if (!Number.isFinite(video.duration) || video.duration <= 0) throw new Error('The video length is unavailable.');
  const target = Math.max(0, Math.min(seconds, lastFrameSeconds, video.duration));
  video.pause();
  video.currentTime = target;
  return target;
}
