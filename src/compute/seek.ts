/** Seek on every click, including the same timestamp twice. Wait for metadata first. */
export async function seekToMoment(video: HTMLVideoElement, seconds: number, lastFrameSeconds: number, signal?: AbortSignal): Promise<number> {
  if (!Number.isFinite(seconds) || !Number.isFinite(lastFrameSeconds) || lastFrameSeconds < 0)
    throw new Error('时间点无效');
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
      const failed = () => done(new Error('视频暂时无法加载，请重新打开结果'));
      const aborted = () => done(new DOMException('Cancelled', 'AbortError'));
      const timer = setTimeout(() => done(new Error('等待视频超时，请重试')), 10000);
      video.addEventListener('loadedmetadata', loaded, { once: true });
      video.addEventListener('error', failed, { once: true });
      signal?.addEventListener('abort', aborted, { once: true });
      video.load();
    });
  }
  if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
  if (!Number.isFinite(video.duration) || video.duration <= 0) throw new Error('视频时长无效');
  const target = Math.max(0, Math.min(seconds, lastFrameSeconds, video.duration));
  video.pause();
  video.currentTime = target;
  return target;
}
