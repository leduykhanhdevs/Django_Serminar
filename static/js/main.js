/**
 * DataShield: Executive Privacy & Compliance Platform
 * Interactive Motion Controller & GSAP Enhancements
 * Guaranteed FOIC-safe (Flash of Invisible Content safety).
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Mandatory FOIC-Safety: Ensure immediate visibility of all layout elements
  document.querySelectorAll(".hero, .feature-card, .metric-card, .content-card, .notice-panel, .hero-panel, .card")
    .forEach(el => {
      el.style.opacity = "1";
      el.style.visibility = "visible";
    });

  // 2. Fallback check for GSAP
  if (typeof gsap === "undefined") {
    return;
  }

  // 3. Respect user accessibility preferences (prefers-reduced-motion)
  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReduced) {
    return;
  }

  // 4. Subtle, professional entrance (translateY ONLY, NO opacity: 0)
  try {
    const heroElements = document.querySelectorAll(".hero h1, .hero .lead, .hero .button-row, .hero-panel");
    if (heroElements.length > 0) {
      gsap.from(heroElements, {
        y: 8,
        duration: 0.35,
        stagger: 0.06,
        ease: "power2.out",
        clearProps: "all"
      });
    }

    const cards = document.querySelectorAll(".metric-card, .feature-card");
    if (cards.length > 0) {
      gsap.from(cards, {
        y: 10,
        duration: 0.4,
        stagger: 0.05,
        ease: "power2.out",
        clearProps: "transform"
      });
    }
  } catch (err) {
    // Non-blocking presentation fallback
  }

  // 5. Telemetry Number Counters (Smooth count up without hiding initial values)
  try {
    const counters = document.querySelectorAll("[data-counter-target]");
    counters.forEach((el) => {
      const target = parseFloat(el.getAttribute("data-counter-target")) || 0;
      const suffix = el.getAttribute("data-counter-suffix") || "";
      const obj = { val: 0 };

      gsap.to(obj, {
        val: target,
        duration: 1.1,
        ease: "power2.out",
        onUpdate: () => {
          el.textContent = Math.round(obj.val) + suffix;
        },
      });
    });
  } catch (err) {
    // Non-blocking
  }

  // 6. Interactive Micro-Interactions: Subtle 1.5px lift (NO neon glow)
  const interactiveCards = document.querySelectorAll(".feature-card, .metric-card, .hero-panel");
  interactiveCards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      gsap.to(card, {
        y: -2,
        duration: 0.18,
        ease: "power1.out",
      });
    });

    card.addEventListener("mouseleave", () => {
      gsap.to(card, {
        y: 0,
        duration: 0.22,
        ease: "power1.out",
      });
    });
  });

  // 7. Flash Alerts Auto-dismiss
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach((flash) => {
    gsap.delayedCall(5, () => {
      gsap.to(flash, {
        x: 30,
        opacity: 0,
        duration: 0.35,
        ease: "power2.in",
        onComplete: () => flash.remove(),
      });
    });
  });
});
