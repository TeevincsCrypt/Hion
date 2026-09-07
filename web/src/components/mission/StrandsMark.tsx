/**
 * A small, tasteful credit: Hion's agents genuinely execute through the
 * Strands Agents SDK runtime (see the backend's `hion/agents/factory.py`,
 * which names every Strands `Agent` instance `hion-{role}`). This is not
 * decorative branding - it is the one place the interface tells a viewer
 * what is actually running the crew.
 */
export function StrandsMark() {
  return (
    <p className="pointer-events-none text-[10px] font-medium uppercase tracking-widest2 text-ink-300">
      Powered by Strands Agents SDK
    </p>
  );
}
