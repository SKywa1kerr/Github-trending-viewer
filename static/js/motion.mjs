// GSAP is served locally. Native controls remain functional if it cannot load.
const engine = () => globalThis.gsap;
const reduced = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const closing = new WeakSet();

export function showDialogMotion(dialog) {
    const gsap = engine();
    if (!gsap || reduced()) return;
    gsap.killTweensOf(dialog);
    gsap.timeline({ defaults: { ease: 'power2.out' } })
        .fromTo(dialog, { y: 12, opacity: .7 }, { y: 0, opacity: 1, duration: .24, clearProps: 'transform,opacity' });
}

export function closeDialogMotion(dialog) {
    if (!dialog.open || closing.has(dialog)) return;
    const gsap = engine();
    if (!gsap || reduced()) { dialog.close(); return; }
    closing.add(dialog);
    gsap.killTweensOf(dialog);
    gsap.to(dialog, {
        y: 8, opacity: 0, duration: .14, ease: 'power1.in',
        onComplete() {
            dialog.close();
            gsap.set(dialog, { clearProps: 'transform,opacity' });
            closing.delete(dialog);
        },
    });
}

export function bindMotionFeedback(root = document) {
    const gsap = engine();
    if (!gsap) return;
    const events = new AbortController();
    const media = gsap.matchMedia();
    const active = new Set();
    const restore = target => {
        if (!active.delete(target)) return;
        gsap.to(target, { scale: 1, duration: .2, ease: 'power2.out', overwrite: true, clearProps: 'transform' });
    };
    media.add('(prefers-reduced-motion: no-preference)', () => {
        const localEvents = new AbortController();
        root.addEventListener('pointerdown', event => {
            if (event.button !== 0) return;
            const target = event.target.closest('button:not(:disabled), .filter-panel > summary');
            if (!target) return;
            active.add(target);
            gsap.to(target, { scale: .96, duration: .1, ease: 'power1.out', overwrite: true });
        }, { signal: localEvents.signal });
        root.addEventListener('pointerup', () => [...active].forEach(restore), { signal: localEvents.signal });
        root.addEventListener('pointercancel', () => [...active].forEach(restore), { signal: localEvents.signal });
        root.addEventListener('pointerout', event => { if (active.has(event.target)) restore(event.target); }, { signal: localEvents.signal });
        globalThis.addEventListener('blur', () => [...active].forEach(restore), { signal: localEvents.signal });
        const panel = root.getElementById('filter-panel');
        panel?.addEventListener('toggle', () => {
            const popover = panel.querySelector('.filter-popover');
            if (panel.open && popover) gsap.fromTo(popover, { y: -5, opacity: .7 }, { y: 0, opacity: 1, duration: .18, ease: 'power2.out', clearProps: 'transform,opacity', overwrite: true });
        }, { signal: localEvents.signal });
        return () => {
            localEvents.abort();
            for (const target of active) { gsap.killTweensOf(target); gsap.set(target, { clearProps: 'transform' }); }
            active.clear();
        };
    });
    globalThis.addEventListener('pagehide', () => { events.abort(); media.revert(); }, { once: true, signal: events.signal });
}
