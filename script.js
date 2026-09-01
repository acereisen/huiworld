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

const sideNav = document.querySelector("#side-nav");
const sideToggle = document.querySelector(".side-toggle");
const sideBackdrop = document.querySelector(".side-nav-backdrop");
let sideAutoClose;

function setSideNav(open) {
  sideNav.classList.toggle("is-open", open);
  sideBackdrop.classList.toggle("is-visible", open);
  sideToggle.setAttribute("aria-expanded", String(open));
  sideToggle.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  clearTimeout(sideAutoClose);
}

sideToggle.addEventListener("click", () => setSideNav(!sideNav.classList.contains("is-open")));
sideBackdrop.addEventListener("click", () => setSideNav(false));
document.addEventListener("keydown", event => {
  if (event.key === "Escape") setSideNav(false);
});
document.querySelectorAll(".side-links a[href^='#']").forEach(link => {
  link.addEventListener("click", () => setSideNav(false));
});

const sectionLinks = [...document.querySelectorAll(".side-links a[href^='#']")];
const sectionObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    sectionLinks.forEach(link => link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`));
  });
}, { rootMargin: "-35% 0px -55%", threshold: 0 });
document.querySelectorAll("main section[id]").forEach(section => sectionObserver.observe(section));

sideAutoClose = setTimeout(() => setSideNav(false), 2500);
