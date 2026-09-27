import { type ReactNode, useId, useLayoutEffect, useRef, useState } from "react";

/**
 * „?“-Symbol mit Erklärtext: erscheint bei Hover, Tastatur-Fokus oder Antippen (Mobil);
 * Escape oder erneutes Antippen schließt ihn.
 */
export function InfoTip({ children, label = "Erklärung" }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [shift, setShift] = useState(0);
  const pop = useRef<HTMLSpanElement>(null);
  const id = useId();
  const visible = open || pinned;

  // am Bildschirmrand nicht abschneiden
  useLayoutEffect(() => {
    if (!visible || !pop.current) return;
    const rect = pop.current.getBoundingClientRect();
    const margin = 12;
    const width = document.documentElement.clientWidth;
    if (rect.right > width - margin) setShift((s) => s - (rect.right - (width - margin)));
    else if (rect.left < margin) setShift((s) => s + (margin - rect.left));
  }, [visible]);

  const close = () => {
    setOpen(false);
    setPinned(false);
    setShift(0);
  };

  return (
    <span className="infotip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => !pinned && close()}>
      <button type="button" className="infotip-btn" aria-label={label} aria-expanded={visible}
        aria-describedby={visible ? id : undefined}
        onClick={() => (pinned ? close() : setPinned(true))}
        onFocus={() => setOpen(true)} onBlur={close}
        onKeyDown={(e) => e.key === "Escape" && close()}>
        ?
      </button>
      {visible && (
        <span ref={pop} role="tooltip" id={id} className="infotip-pop" style={{ transform: `translateX(${shift}px)` }}>
          {children}
        </span>
      )}
    </span>
  );
}
