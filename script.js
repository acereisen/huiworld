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
