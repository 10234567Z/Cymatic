export default function Home() {
  return (
    <div className="hero-bg grain min-h-screen">
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-8 md:px-10">
        <header className="mb-12 flex items-center justify-start">
          <div className="pill">
            <span className="pulse-dot" aria-hidden />
            0G Testnet Live
          </div>
        </header>

        <section className="grid flex-1 items-center gap-8 md:grid-cols-[1.15fr_0.85fr]">
          <div>
            <p className="mb-3 text-sm uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              Cymatic
            </p>
            <h1 className="section-title mb-4 text-5xl leading-[1.02] md:text-7xl">
              Voice-first
              <br />
              iNFT Infra
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-[var(--ink-soft)] md:text-xl">
              Phone calls become on-chain identity actions. Cymatic creates and tracks caller
              iNFTs on 0G, then lets your agent stack react in real time.
            </p>
            <div className="mt-8">
              <a
                href="https://explorer.0g.ai/testnet/blockchain/accounts/0xfb61896b0521594b49f261c96bd0313ce32d70e7/transactions"
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-full bg-[var(--accent)] px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-[var(--accent-deep)]"
              >
                View Cymatic iNFT Contract
              </a>
            </div>
          </div>

          <div className="card p-6 md:p-8">
            <h2 className="section-title mb-4 text-2xl">What Cymatic Does</h2>
            <ul className="space-y-3 text-[15px] leading-relaxed text-[var(--ink-soft)]">
              <li>
                1. Creates caller-bound iNFT identities from voice onboarding.
              </li>
              <li>
                2. Connects voice workflow with wallet and contract operations.
              </li>
              <li>
                3. Keeps the interaction flow fast, simple, and agent-ready.
              </li>
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}
