/**
 * DataShield: Enterprise Privacy & Compliance Platform
 * Interactive Animations & GSAP Controller
 * UIT Course: Django Cơ Bản (4 tín chỉ) - Đồ án Seminar
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Verify GSAP availability
  if (typeof gsap === "undefined") {
    console.warn("GSAP is not loaded. Skipping animations.");
    return;
  }

  // 2. Set up matchMedia for accessibility (respect prefers-reduced-motion)
  const mm = gsap.matchMedia();

  mm.add("(prefers-reduced-motion: no-preference)", () => {
    // Master timeline for initial load
    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

    // Stagger Header / Navbar elements
    if (document.querySelector(".site-header")) {
      tl.from(".site-header", {
        y: -18,
        opacity: 0,
        duration: 0.6,
      });
    }

    // Hero Section Sequence
    const hero = document.querySelector(".hero");
    if (hero) {
      tl.from(".hero .eyebrow", {
        y: 12,
        opacity: 0,
        duration: 0.5,
      }, "-=0.2")
      .from(".hero h1", {
        y: 20,
        opacity: 0,
        duration: 0.7,
        letterSpacing: "0.02em",
      }, "-=0.3")
      .from(".hero .lead", {
        y: 16,
        opacity: 0,
        duration: 0.6,
      }, "-=0.4")
      .from(".hero .button-row a", {
        y: 12,
        opacity: 0,
        stagger: 0.1,
        duration: 0.5,
      }, "-=0.3")
      .from(".hero-panel", {
        x: 30,
        opacity: 0,
        duration: 0.8,
        ease: "power2.out",
      }, "-=0.6")
      .from(".hero-panel li", {
        x: 15,
        opacity: 0,
        stagger: 0.08,
        duration: 0.4,
      }, "-=0.4");
    }

    // Metric Cards Stagger & Counter Animation
    const metricCards = document.querySelectorAll(".metric-card");
    if (metricCards.length > 0) {
      tl.from(metricCards, {
        y: 25,
        opacity: 0,
        stagger: 0.1,
        duration: 0.6,
        ease: "back.out(1.2)",
      }, "-=0.3");

      // Animate numeric counters if present
      const counters = document.querySelectorAll("[data-counter-target]");
      counters.forEach((el) => {
        const target = parseFloat(el.getAttribute("data-counter-target")) || 0;
        const suffix = el.getAttribute("data-counter-suffix") || "";
        const obj = { val: 0 };

        gsap.to(obj, {
          val: target,
          duration: 1.6,
          ease: "power2.out",
          delay: 0.4,
          onUpdate: () => {
            el.textContent = Math.round(obj.val) + suffix;
          },
        });
      });
    }

    // Three-up Feature Cards Stagger
    const featureCards = document.querySelectorAll(".feature-card");
    if (featureCards.length > 0) {
      tl.from(featureCards, {
        y: 30,
        opacity: 0,
        stagger: 0.12,
        duration: 0.7,
        ease: "power2.out",
      }, "-=0.3");
    }

    // Notice & Legal Panels
    const noticePanels = document.querySelectorAll(".notice-panel, .legal-notice");
    if (noticePanels.length > 0) {
      tl.from(noticePanels, {
        y: 18,
        opacity: 0,
        stagger: 0.15,
        duration: 0.6,
      }, "-=0.2");
    }

    // Dashboard Content Cards
    const contentCards = document.querySelectorAll(".content-card");
    if (contentCards.length > 0) {
      tl.from(contentCards, {
        y: 20,
        opacity: 0,
        stagger: 0.1,
        duration: 0.6,
      }, "-=0.2");
    }
  });

  // 3. Interactive Micro-Interactions: Card Tilt & Hover Glow
  const cards = document.querySelectorAll(".feature-card, .hero-panel");
  cards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      gsap.to(card, {
        y: -4,
        boxShadow: "0 16px 36px -6px rgba(0, 0, 0, 0.6), 0 0 24px rgba(56, 189, 248, 0.2)",
        duration: 0.25,
        ease: "power1.out",
      });
    });

    card.addEventListener("mouseleave", () => {
      gsap.to(card, {
        y: 0,
        boxShadow: "0 8px 24px -4px rgba(0, 0, 0, 0.45)",
        duration: 0.35,
        ease: "power1.out",
      });
    });
  });

  // 4. Flash Message Auto-dismiss with GSAP
  const flashes = document.querySelectorAll(".flash");
  if (flashes.length > 0) {
    flashes.forEach((flash) => {
      // Auto dismiss after 6 seconds
      gsap.delayedCall(6, () => {
        gsap.to(flash, {
          x: 60,
          opacity: 0,
          duration: 0.5,
          ease: "power2.in",
          onComplete: () => flash.remove(),
        });
      });
    });
  }

  // 5. Log initialization for audit verification
  console.info("🛡️ DataShield: Enterprise Privacy UI & GSAP Engine initialized successfully.");
});
