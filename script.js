document.getElementById("year").textContent = new Date().getFullYear();

const navToggle = document.getElementById("navToggle");
const navLinks = document.getElementById("navLinks");

navToggle.addEventListener("click", () => {
  const isOpen = navLinks.classList.toggle("open");
  navToggle.setAttribute("aria-expanded", isOpen);
});

navLinks.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    navLinks.classList.remove("open");
    navToggle.setAttribute("aria-expanded", "false");
  });
});

const backToTop = document.getElementById("backToTop");

window.addEventListener("scroll", () => {
  backToTop.classList.toggle("visible", window.scrollY > 400);
});

backToTop.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// Cookie jar footer easter egg — purely for fun, no data is collected.
const jarCookies = document.getElementById("jarCookies");
const cookieToast = document.getElementById("cookieToast");
const jarRefill = document.getElementById("jarRefill");
const cookieHint = document.getElementById("cookieHint");

const cookieMessages = [
  "Cookie taken! 🍪 (the only tracking here is crumbs)",
  "Enjoy! No data was harmed in the making of this cookie.",
  "Yum — zero calories, zero cookies stored on your device.",
  "Take one, no consent form required.",
  "Freshly baked, never tracked.",
];

let toastTimeout;
function showToast(message) {
  clearTimeout(toastTimeout);
  cookieToast.textContent = message;
  cookieToast.classList.add("visible");
  toastTimeout = setTimeout(() => cookieToast.classList.remove("visible"), 2200);
}

function takeCookie(cookie) {
  if (cookie.classList.contains("taken")) return;
  cookie.classList.add("taken");
  showToast(cookieMessages[Math.floor(Math.random() * cookieMessages.length)]);

  const remaining = jarCookies.querySelectorAll(".cookie:not(.taken)").length;
  if (remaining === 0) {
    cookieHint.textContent = "The jar's empty — thanks for visiting!";
    jarRefill.hidden = false;
  }
}

if (jarCookies) {
  jarCookies.querySelectorAll(".cookie").forEach((cookie) => {
    cookie.addEventListener("click", () => takeCookie(cookie));
    cookie.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        takeCookie(cookie);
      }
    });
  });
}

if (jarRefill) {
  jarRefill.addEventListener("click", () => {
    jarCookies.querySelectorAll(".cookie").forEach((cookie) => cookie.classList.remove("taken"));
    jarRefill.hidden = true;
    cookieHint.innerHTML = "Psst — take a cookie 🍪<br>(no data collected, pinkie promise)";
  });
}
