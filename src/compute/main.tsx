import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { seekToMoment } from './seek';
import './review.css';

import { api, type Session } from '../api';
import type { Moment, Task, Note } from './results';
const limbLabel: Record<string, string> = { left_hand: '左手', right_hand: '右手', left_foot: '左脚', right_foot: '右脚' };
function Review() {
  const [csrf, setCsrf] = useState('');
  const submit = (path: string, body: unknown) => api<Task>(path, {
    method: 'POST', csrf, headers: { 'Idempotency-Key': crypto.randomUUID() }, body,
  });
  const [user, setUser] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [height, setHeight] = useState(170);
  const [span, setSpan] = useState(175);
  const [notice, setNotice] = useState('');
  const player = useRef<HTMLVideoElement>(null);
  const pendingSeek = useRef<AbortController | null>(null);
  const task = tasks.find(t => t.id === selected);
  const result = task?.result;

  async function attempt(action: () => Promise<void>) {
    setError(''); setBusy(true);
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function refresh(signal?: AbortSignal) {
    const [jobs, notifications] = await Promise.all([
      api<{ items: Task[] }>('/tasks?limit=100', { signal }),
      api<{ items: Note[] }>('/notifications?limit=100', { signal }),
    ]);
    setTasks(jobs.items); setNotes(notifications.items);
  }
  useEffect(() => {
    api<Session>('/auth/me').then(data => {
      setCsrf(data.csrf_token); setUser(data.user.username);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await refresh(controller.signal); }
      catch (e) { if (!controller.signal.aborted) setError((e as Error).message); }
      if (!controller.signal.aborted) timer = setTimeout(poll, document.hidden ? 10000 : 2000);
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [user]);
  useEffect(() => {
    pendingSeek.current?.abort(); setNotice('');
    return () => pendingSeek.current?.abort();
  }, [selected]);
  async function auth(register: boolean) {
    const data = await api<Session>('/auth/' + (register ? 'register' : 'login'), {
      method: 'POST', body: { username, password },
    });
    setCsrf(data.csrf_token); setPassword(''); setUser(data.user.username);
  }
  async function upload() {
    if (!file) throw new Error('请先选择 Trial 2 原视频');
    const form = new FormData(); form.set('video', file); form.set('route_id', 'r1'); form.set('visibility', 'private');
    const video = await api<{ id: string }>('/videos', { method: 'POST', body: form, csrf });
    const created = await submit('/tasks/analyze', { kind: 'analyze', video_id: video.id, route_id: 'r1',
      calibration: { version: 'trial2-grid143-v2', reference_frame: 450, evidence_key: 'calibration/trial2-grid143-v2' } });
    await refresh(); setSelected(created.id);
  }
  async function generate() {
    if (!task) return;
    const source = await api<{ source_analysis_id: string; source_analysis_version: string }>('/tasks/source-analysis/' + task.source_video_id);
    const created = await submit('/tasks/generate', { kind: 'generate', video_id: task.source_video_id, source_analysis_id: source.source_analysis_id, source_analysis_version: source.source_analysis_version,
      target_body: { height_cm: height, arm_span_cm: span, provenance: 'user_input' }, compare_techniques: true });
    await refresh(); setSelected(created.id);
  }
  async function jump(moment: Moment) {
    if (!player.current || !result) return;
    pendingSeek.current?.abort(); const controller = new AbortController(); pendingSeek.current = controller;
    try {
      const seconds = await seekToMoment(player.current, moment.at_seconds, (result.frame_count - 1) / result.fps, controller.signal);
      setNotice(`已定位 ${seconds.toFixed(2)} 秒 · ${limbLabel[moment.limb] || moment.limb}`);
    } catch (e) { if ((e as Error).name !== 'AbortError') setError((e as Error).message); }
  }
  return <main>
    <header><h1>BetaLab · 算法联调</h1><p>真实任务、视频与时间点核查。当前支持校准过的 Trial 2；生成预览不等于动作可行。</p></header>
    {error && <p role="alert">{error}</p>}
    {!user ? <section><h2>登录</h2>
      <label>用户名<input aria-label="用户名" value={username} onChange={e => setUsername(e.target.value)} /></label>
      <label>密码<input aria-label="密码" type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button disabled={busy} onClick={() => void attempt(() => auth(false))}>登录</button>
      <button disabled={busy} onClick={() => void attempt(() => auth(true))}>注册测试账号</button>
    </section> : <>
      <p>当前用户：{user} <button onClick={() => void attempt(async () => {
        await api('/auth/logout', { method: 'POST', csrf }); setCsrf(''); setUser(''); setTasks([]); setSelected('');
      })}>退出</button></p>
      <section><h2>提交真实分析</h2><p>视频默认私有；源身材未填写时明确标注为估计。</p>
        <input aria-label="Trial 2 视频" type="file" accept="video/mp4,video/quicktime" onChange={e => setFile(e.target.files?.[0] || null)} />
        <button disabled={busy || !file} onClick={() => void attempt(upload)}>上传并分析</button>
      </section>
      <div className="columns"><aside><section><h2>我的任务</h2>{tasks.map(t => <button className="row" key={t.id} onClick={() => setSelected(t.id)}>
        {t.kind === 'analyze' ? '源分析' : '个性化预览'} · {t.state} {t.is_mock && '（模拟）'}
      </button>)}</section><section><h2>通知</h2>{notes.map(n => <button className="row" key={n.id} onClick={() => void attempt(async () => {
        setSelected(n.task_id); await api('/notifications/' + n.id + '/read', { method: 'PATCH', csrf }); await refresh();
      })}>{n.read_at ? '已读' : '未读'} · {n.event === 'task_succeeded' ? '计算完成' : '任务失败'}</button>)}</section></aside>
      <section><h2>结果与时间点</h2>{task && <>
        <p data-testid="task-state">{task.kind} · {task.state} · {task.stage}</p>
        {task.error && <p role="alert">{task.error.message}</p>}
        {task.error?.retryable && <button disabled={busy} onClick={() => void attempt(async () => {
          const retried = await submit('/tasks/' + task.id + '/retry', {}); await refresh(); setSelected(retried.id);
        })}>重试任务</button>}
        {result && <>
          <p data-testid="baseline">{result.is_mock ? '模拟结果' : '真实计算结果'} · 基线：{result.baseline_status}</p>
          {result.quality.warnings.map(w => <p className="warning" key={w}>{w}</p>)}
          {Boolean(result.artifacts.video) && <video key={task.id} ref={player} aria-label="生成结果" controls preload="metadata"
            src={'/api/tasks/' + task.id + '/artifacts/video'} onError={() => setError('视频无法读取；请确认源视频权限后重新打开结果。')} />}
          <p aria-live="polite">{notice}</p>
          <h3>需要核查的片段</h3><p>以下是模型诊断，不是未经证实的技巧建议。</p>
          {(result.moments || []).map(m => <div key={m.id} className="moment"><button data-frame={m.frame} data-seconds={m.at_seconds} onClick={() => void jump(m)}>
            查看 {m.at_seconds.toFixed(2)} 秒 · {limbLabel[m.limb] || m.limb} · {m.title}</button><p>{m.explanation}</p></div>)}
          <label>目标身高（cm）<input aria-label="目标身高" type="number" min={100} max={230} value={height} onChange={e => setHeight(Number(e.target.value))} /></label>
          <label>目标臂展（cm）<input aria-label="目标臂展" type="number" min={80} max={260} value={span} onChange={e => setSpan(Number(e.target.value))} /></label>
          <button disabled={busy} onClick={() => void attempt(generate)}>生成我的预览</button>
        </>}
      </>}</section></div>
    </>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<Review />);
