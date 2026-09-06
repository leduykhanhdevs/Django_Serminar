/**
 * DataShield: Enterprise Privacy & Compliance Platform
 * Interactive Animations & GSAP Controller
 * Rock-solid visibility: Zero FOUC / Zero FOIC. All elements visible by default.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Ensure all elements are immediately visible
  document.querySelectorAll(".hero, .feature-card, .metric-card, .content-card, .notice-panel, .hero-panel")
    .forEach(el => {
      el.style.opacity = "1";
      el.style.visibility = "visible";
    });

  // Verify GSAP availability
  if (typeof gsap === "undefined") {
    console.info("GSAP running in static fallback mode.");
    return;
  }

  // Check prefers-reduced-motion
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReduced) {
    console.info("Reduced motion active. Animations disabled.");
    return;
  }

  // 1. Subtle, high-performance entrance (ONLY translateY, NEVER opacity 0)
  try {
    const heroElements = document.querySelectorAll(".hero h1, .hero .lead, .hero .button-row, .hero-panel");
    if (heroElements.length > 0) {
      gsap.from(heroElements, {
        y: 12,
        duration: 0.4,
        stagger: 0.08,
        ease: "power2.out",
        clearProps: "all"
      });
    }

    const cards = document.querySelectorAll(".metric-card, .feature-card");
    if (cards.length > 0) {
      gsap.from(cards, {
        y: 16,
        duration: 0.45,
        stagger: 0.06,
        ease: "power2.out",
        clearProps: "transform"
      });
    }
  } catch (err) {
    console.warn("GSAP entrance notice:", err);
  }

  // 2. Telemetry Number Counters (Smooth count up without hiding initial values)
  try {
    const counters = document.querySelectorAll("[data-counter-target]");
    counters.forEach((el) => {
      const target = parseFloat(el.getAttribute("data-counter-target")) || 0;
      const suffix = el.getAttribute("data-counter-suffix") || "";
      const obj = { val: 0 };

      gsap.to(obj, {
        val: target,
        duration: 1.2,
        ease: "power2.out",
        onUpdate: () => {
          el.textContent = Math.round(obj.val) + suffix;
        },
      });
    });
  } catch (err) {
    console.warn("Counter animation notice:", err);
  }

  // 3. Interactive Micro-Interactions: Card Tilt & Subtle Glow
  const interactiveCards = document.querySelectorAll(".feature-card, .metric-card, .hero-panel");
  interactiveCards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      gsap.to(card, {
        y: -3,
        duration: 0.2,
        ease: "power1.out",
      });
    });

    card.addEventListener("mouseleave", () => {
      gsap.to(card, {
        y: 0,
        duration: 0.25,
        ease: "power1.out",
      });
    });
  });

  // 4. Flash Alerts Auto-dismiss
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach((flash) => {
    gsap.delayedCall(5, () => {
      gsap.to(flash, {
        x: 40,
        opacity: 0,
        duration: 0.4,
        ease: "power2.in",
        onComplete: () => flash.remove(),
      });
    });
  });

  console.info("🛡️ DataShield UI & GSAP Engine initialized.");
});
