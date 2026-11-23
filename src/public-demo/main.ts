import cases from './cases.json'
import './style.css'

const root = document.querySelector<HTMLDivElement>('#demo-root')!
root.innerHTML = `
  <header class="topbar"><a class="brand" href="./demo.html" aria-label="BetaLab demos home"><span class="brand-mark">β</span> BetaLab</a><span class="access">Public demo · No sign-in</span></header>
  <main>
    <section class="intro"><p class="eyebrow">A DIFFERENT WAY TO SEE THE CLIMB</p><h1>Watch the move.<br><span>Explore the skeleton.</span></h1><p class="lead">Three climbing studies, with the original recording and a prepared skeleton on the same timeline.</p></section>
    <nav class="cases" aria-label="Choose a climbing demo">${cases.map((c,i) => `<button type="button" data-case="${c.id}" aria-pressed="false"><img src="${import.meta.env.BASE_URL+c.wall}" alt="" loading="lazy"><span><small>STUDY 0${i+1}</small><strong>${c.name}</strong><em>${c.seconds.toFixed(1)} sec · ${c.view}</em></span><b aria-hidden="true">↗</b></button>`).join('')}</nav>
    <section class="viewer" aria-label="Selected demonstration">
      <div class="viewer-heading"><div><p class="eyebrow">PRE-GENERATED DEMONSTRATION</p><h2 id="case-title"></h2></div><span class="view-badge" id="case-view"></span></div>
      <div class="viewer-body"><div class="player-wrap"><video id="demo-player" controls playsinline preload="metadata" aria-label="Skeleton and original video comparison"></video><p id="media-error" role="alert" hidden>Video could not load. Please try reloading the page or opening the video directly.</p></div>
      <aside><h3>One timeline. Two views.</h3><p><span class="step">01</span><strong>Skeleton above</strong><br>Focused on the movement and contact holds.</p><p><span class="step">02</span><strong>Original below</strong><br>The complete recording, synchronized with the skeleton.</p><div class="measurements"><small>PREPARED MODEL</small><p id="body-label"></p></div><p class="note">This is a saved research preview, not a new result generated for your body. Model warnings remain; climbing feasibility and technique improvements are not verified.</p><a id="video-link" target="_blank" rel="noreferrer">Open full-size video ↗</a></aside></div>
      <details><summary>About these demonstrations</summary><p>Trial 1 and Trial 3 show planar (2D) model trajectories at 180 cm height with template proportions. Their original climbers’ measurements are unknown. Corner Study shows a historical 3D diagnostic; its geometric baseline has not passed. These videos do not identify confirmed climbing techniques.</p><p>This public page plays prepared videos only. It does not log you in, upload videos, run algorithms, or save personal data. Route venues are not independently verified.</p></details>
    </section>
    <footer><span>BetaLab · Climbing movement studies</span><span>Based on the CIS5810 Beta Translator project</span></footer>
  </main>`
const player = document.querySelector<HTMLVideoElement>('#demo-player')!
const error = document.querySelector<HTMLElement>('#media-error')!
function select(id: string) {
  const c = cases.find(c => c.id === id) ?? cases[0]
  player.pause()
  error.hidden = true
  document.querySelector('#case-title')!.textContent = c.name
  document.querySelector('#case-view')!.textContent = c.view
  document.querySelector('#body-label')!.textContent = `${c.height} cm height · ${c.span == null ? 'Template arm proportions' : `${c.span} cm arm span`}`
  player.poster = import.meta.env.BASE_URL + c.poster
  player.src = import.meta.env.BASE_URL + c.video
  document.querySelector<HTMLAnchorElement>('#video-link')!.href = player.src
  document.querySelectorAll<HTMLButtonElement>('[data-case]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.case === c.id)))
}
document.querySelectorAll<HTMLButtonElement>('[data-case]').forEach(button => button.addEventListener('click', () => {
  history.replaceState(null, '', '#' + button.dataset.case)
  select(button.dataset.case!)
}))
player.addEventListener('error', () => { error.hidden = false })
window.addEventListener('hashchange', () => select(location.hash.slice(1)))
select(location.hash.slice(1))
