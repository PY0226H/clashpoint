export function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="echo-placeholder-page">
      <h2>{title}</h2>
      <p>This module has been scheduled in the migration matrix and will be moved from legacy Vue flow next.</p>
    </section>
  );
}
