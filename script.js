const roles = ["Battery Intelligence", "Energy Analytics", "Data Engineering", "Renewable Systems"];
const role = document.querySelector("#dynamic-role");
let roleIndex = 0;
setInterval(() => {
  role.classList.add("swap");
  setTimeout(() => {
    roleIndex = (roleIndex + 1) % roles.length;
    role.textContent = roles[roleIndex];
    role.classList.remove("swap");
  }, 280);
}, 2400);

const revealObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll(".reveal").forEach(el => revealObserver.observe(el));

const glow = document.querySelector(".cursor-glow");
window.addEventListener("pointermove", e => {
  glow.style.transform = `translate(${e.clientX - 180}px,${e.clientY - 180}px)`;
});

document.querySelectorAll(".tilt").forEach(card => {
  card.addEventListener("pointermove", e => {
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - .5;
    const y = (e.clientY - r.top) / r.height - .5;
    card.style.transform = `perspective(700px) rotateX(${-y * 5}deg) rotateY(${x * 7}deg) translateY(-4px)`;
  });
  card.addEventListener("pointerleave", () => card.style.transform = "");
});

const portraitCard = document.querySelector(".portrait-card");
const portraitImage = portraitCard?.querySelector("img");
const matrixCanvas = portraitCard?.querySelector(".portrait-matrix");
const matrixReplay = portraitCard?.querySelector(".matrix-replay");

if (portraitCard && portraitImage && matrixCanvas) {
  const matrixContext = matrixCanvas.getContext("2d", { alpha: true });
  const sampleCanvas = document.createElement("canvas");
  const sampleContext = sampleCanvas.getContext("2d", { willReadFrequently: true });
  let animationStarted = false;

  const startMatrixReveal = () => {
    if (animationStarted) return;
    animationStarted = true;
    portraitCard.classList.remove("decoded", "colorizing", "photo-emerging");
    matrixCanvas.hidden = false;
    matrixCanvas.style.opacity = "1";
    if (matrixReplay) {
      matrixReplay.disabled = true;
      matrixReplay.textContent = "DECODING...";
    }

    const rect = portraitCard.getBoundingClientRect();
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const cell = width < 270 ? 8 : 9;
    const columns = Math.ceil(width / cell);
    const rows = Math.ceil(height / cell);

    matrixCanvas.width = Math.round(width * pixelRatio);
    matrixCanvas.height = Math.round(height * pixelRatio);
    matrixContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    sampleCanvas.width = columns;
    sampleCanvas.height = rows;
    sampleContext.filter = "grayscale(1) contrast(1.15)";
    const sourceRatio = portraitImage.naturalWidth / portraitImage.naturalHeight;
    const targetRatio = columns / rows;
    let sourceX = 0;
    let sourceY = 0;
    let sourceWidth = portraitImage.naturalWidth;
    let sourceHeight = portraitImage.naturalHeight;
    if (sourceRatio > targetRatio) {
      sourceWidth = sourceHeight * targetRatio;
      sourceX = (portraitImage.naturalWidth - sourceWidth) / 2;
    } else {
      sourceHeight = sourceWidth / targetRatio;
      sourceY = (portraitImage.naturalHeight - sourceHeight) * .25;
    }
    sampleContext.drawImage(portraitImage, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, columns, rows);
    const pixels = sampleContext.getImageData(0, 0, columns, rows).data;
    const glyphs = ["0", "1", "0", "1", "+", "."];
    const particles = [];
    for (let row = 0; row < rows; row++) {
      for (let column = 0; column < columns; column++) {
        const index = row * columns + column;
        const pixelIndex = index * 4;
        const luminance = (pixels[pixelIndex] * .2126 + pixels[pixelIndex + 1] * .7152 + pixels[pixelIndex + 2] * .0722) / 255;
        const darkness = 1 - luminance;
        if (Math.random() > .06 + darkness * .88) continue;
        const spawn = .08 + Math.random() * .28;
        particles.push({
          x: column * cell + cell / 2,
          y: row * cell + cell / 2,
          startY: -cell * (2 + Math.random() * 22),
          spawn,
          settle: Math.min(.57, spawn + .16 + Math.random() * .20),
          glyph: glyphs[Math.floor(Math.min(glyphs.length - 1, luminance * glyphs.length))],
          alpha: .3 + darkness * .7,
          sway: (Math.random() - .5) * cell * 2.4,
          phase: Math.random() * Math.PI * 2
        });
      }
    }
    const startTime = performance.now();
    const duration = 7600;

    const drawFrame = now => {
      const progress = Math.min(1, (now - startTime) / duration);
      matrixContext.clearRect(0, 0, width, height);
      matrixContext.textAlign = "center";
      matrixContext.textBaseline = "middle";
      matrixContext.font = `700 ${Math.max(9, cell - 2)}px ui-monospace, SFMono-Regular, Consolas, monospace`;

      for (const particle of particles) {
        if (progress < particle.spawn) continue;
        const travel = Math.min(1, (progress - particle.spawn) / (particle.settle - particle.spawn));
        const eased = 1 - Math.pow(1 - travel, 3);
        const x = particle.x + particle.sway * (1 - eased) * Math.sin(particle.phase + travel * 5);
        const y = particle.startY + (particle.y - particle.startY) * eased;
        const flicker = travel < 1 && Math.random() < .035 ? (particle.glyph === "0" ? "1" : "0") : particle.glyph;
        matrixContext.fillStyle = `rgba(16,20,24,${particle.alpha * Math.min(1, travel * 2.5)})`;
        matrixContext.fillText(flicker, x, y);
      }

      if (progress > .66) {
        portraitCard.classList.add("photo-emerging");
        matrixCanvas.style.opacity = String(Math.max(0, 1 - (progress - .66) / .22));
      }
      if (progress > .88) portraitCard.classList.add("colorizing");
      if (progress < 1) {
        requestAnimationFrame(drawFrame);
      } else {
        matrixCanvas.hidden = true;
        portraitCard.classList.add("decoded");
        animationStarted = false;
        if (matrixReplay) {
          matrixReplay.disabled = false;
          matrixReplay.textContent = "REPLAY DECODE";
        }
      }
    };

    requestAnimationFrame(drawFrame);
  };

  const matrixObserver = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      if (portraitImage.complete) startMatrixReveal();
      else portraitImage.addEventListener("load", startMatrixReveal, { once: true });
      matrixObserver.disconnect();
    }
  }, { threshold: .35 });

  matrixObserver.observe(portraitCard);
  matrixReplay?.addEventListener("click", startMatrixReveal);
} else if (portraitCard) {
  portraitCard.classList.add("decoded", "colorizing");
}
