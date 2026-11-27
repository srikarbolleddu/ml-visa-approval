import { ExplorePanel, TabularDemo } from "@srikarbolleddu/ml-demo-kit";
import { client, isLive } from "./client";

const CASE_STUDY =
  "https://srikarbolleddu.com/projects/visa-approval-prediction";
const REPO = "https://github.com/srikarbolleddu/ml-visa-approval";
const DATASET = "https://www.dol.gov/agencies/eta/foreign-labor/performance";

export function App() {
  return (
    <div className="page">
      <nav className="topbar" aria-label="Site">
        <a href={CASE_STUDY}>← Back to the case study</a>
        <a href={REPO} target="_blank" rel="noopener noreferrer">
          View code <span aria-hidden="true">↗</span>
          <span className="visually-hidden"> (opens in a new tab)</span>
        </a>
      </nav>

      <header className="intro">
        <p className="eyebrow">Live demo · Gradient boosting</p>
        <h1>Will this work-visa application be certified?</h1>
        <p>
          Before a US employer can sponsor a foreign worker for a green card,
          the Department of Labor must certify the job (PERM). About 1 in 19
          applications in FY2024 were denied. This model, trained on 90,000
          real decisions, estimates the chance of certification and shows which
          inputs moved it. It never sees the worker&apos;s nationality. Pick a
          real application below or change any input.
        </p>
      </header>

      {!isLive && (
        <p className="notice" role="note">
          Showing predictions recorded from the model. The live model API isn't
          connected yet, so edited inputs return the closest recorded example.
        </p>
      )}

      <section aria-labelledby="try" className="section">
        <h2 id="try">Try it</h2>
        <TabularDemo client={client} hideHeader />
      </section>

      <section aria-labelledby="explore" className="section">
        <h2 id="explore">Explore the model</h2>
        <ExplorePanel client={client} />
      </section>

      <footer className="footer">
        <p>
          Project from the UT Austin Post-Graduate Program in AI &amp; Machine
          Learning, rebuilt from scratch on public government data. A
          demonstration, not legal advice.
        </p>
        <p>
          Data:{" "}
          <a href={DATASET} target="_blank" rel="noopener noreferrer">
            US DOL OFLC PERM disclosure data
          </a>
          , FY2024 (public domain). Nothing you enter is stored.
        </p>
      </footer>
    </div>
  );
}
