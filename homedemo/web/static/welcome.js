(() => {
  const video = document.querySelector('#walkthrough-video');
  const play = document.querySelector('#play-video');
  const status = document.querySelector('#video-status');
  play.hidden = false;
  play.addEventListener('click', async () => {
    try { await video.play(); }
    catch { status.textContent = 'Use the video controls below to play the walkthrough.'; }
  });
  video.addEventListener('play', () => { play.hidden = true; status.textContent = ''; });
  video.addEventListener('ended', () => { status.textContent = 'Ready to explore? Launch the live demo below.'; });
  video.addEventListener('error', () => {
    play.hidden = true;
    status.replaceChildren('The video could not load. ', Object.assign(document.createElement('a'), {
      href: '/static/assets/welcome/unspoken.mp4', textContent: 'Open the video directly',
    }), ', or launch the live demo below.');
  });
})();
