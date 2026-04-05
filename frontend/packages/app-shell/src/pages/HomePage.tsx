import { SectionTitle } from "@echoisle/ui";

const PHASE_CARDS = [
  {
    title: "Phase 0",
    detail: "PRD mapping, API readiness matrix, IA alignment."
  },
  {
    title: "Phase 1",
    detail: "Tokens, UI primitives, shell templates."
  },
  {
    title: "Phase 2",
    detail: "Web/Desktop shared React + TS trunk."
  }
];

export function HomePage() {
  return (
    <section className="echo-home">
      <header>
        <SectionTitle>Mac/Web Migration Workbench</SectionTitle>
        <p>
          This workspace is now driven by shared packages. Next steps are progressive page migration from legacy
          Vue views into React domain modules.
        </p>
      </header>

      <div className="echo-phase-grid">
        {PHASE_CARDS.map((item) => (
          <article className="echo-phase-item" key={item.title}>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>

      <section className="echo-roadmap-strip">
        <p>Current milestone</p>
        <strong>React shell + auth route closure for Web and Mac</strong>
      </section>
    </section>
  );
}
