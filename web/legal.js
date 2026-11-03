// Fills the contact e-mail and limits on the legal pages from the server settings.
(async () => {
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    if (!r.ok) return;
    const h = await r.json();
    if (h.contact_email) {
      document.querySelectorAll("[data-contact]").forEach((el) => {
        el.hidden = false;
        if (el.tagName === "A") el.href = `mailto:${h.contact_email}`;
        if (el.hasAttribute("data-contact-text")) el.textContent = h.contact_email;
      });
    }
    document.querySelectorAll("[data-limit]").forEach((el) => {
      const v = h.limits && h.limits[el.dataset.limit];
      if (v !== undefined) el.textContent = v;
    });
  } catch { /* page still readable */ }
})();
