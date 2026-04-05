import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="echo-placeholder-page">
      <h2>Page not found</h2>
      <p>The target route is not mapped in the React shell yet.</p>
      <Link className="echo-inline-link" to="/home">
        Return home
      </Link>
    </section>
  );
}
