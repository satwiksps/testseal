import { CopyButton } from "./components/copy-button";
import { MobileMenu } from "./components/mobile-menu";
import { DOCUMENTATION_URL, PYPI_URL, REPOSITORY_URL } from "./site-config";
import { getSiteUrl } from "./site-url";
import packageMetadata from "../package.json";

const RELEASE_VERSION = packageMetadata.version;
const RELEASE_REF = `v${RELEASE_VERSION}`;
const ACTION_COMMIT = "89a2ab087ad1b93b6cf26ef2851dc44d8712fc02";

const rules = [
  {
    id: "TS001",
    title: "Assertion removed",
    description: "A previously enforced condition disappears from a test.",
    severity: "High",
  },
  {
    id: "TS002",
    title: "Test disabled",
    description: "A skip, skipif, xfail, or unittest marker is introduced.",
    severity: "High",
  },
  {
    id: "TS003",
    title: "Assertion weakened",
    description: "A precise comparison becomes a truthy or non-null check.",
    severity: "High",
  },
  {
    id: "TS004",
    title: "Tolerance widened",
    description: "Numeric tolerance grows or decimal precision drops.",
    severity: "High",
  },
  {
    id: "TS005",
    title: "Exception swallowed",
    description: "A broad handler can fall through without validation.",
    severity: "High",
  },
  {
    id: "TS006",
    title: "Snapshot regenerated",
    description: "Snapshot update behavior or an artifact enters the diff.",
    severity: "Low",
  },
  {
    id: "TS007",
    title: "Subject mocked",
    description: "A new patch target overlaps with the behavior under test.",
    severity: "Medium",
  },
  {
    id: "TS008",
    title: "Guard co-edited",
    description: "Source and its configured guarding test change together.",
    severity: "Low",
  },
] as const;

const severityStyles = {
  High: "text-rose-300",
  Medium: "text-amber-300",
  Low: "text-zinc-400",
} as const;

const actionWorkflow = [
  "name: Test integrity",
  "on: [pull_request]",
  "permissions:",
  "  contents: read",
  "jobs:",
  "  testseal:",
  "    runs-on: ubuntu-latest",
  "    steps:",
  "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
  "        with:",
  "          fetch-depth: 0",
  "      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
  "        with:",
  '          python-version: "3.12"',
  "      - uses: satwiksps/testseal@" + ACTION_COMMIT + " # " + RELEASE_REF,
  "        with:",
  "          fail-on: high",
].join("\n");

const integrations = [
  {
    name: "CLI",
    title: "Review a branch locally",
    description: "Run the same analyzer before opening a pull request.",
    file: "terminal",
    command: "testseal scan --base origin/main --head HEAD",
  },
  {
    name: "pre-commit",
    title: "Inspect staged changes",
    description: "Keep the default advisory posture or set a threshold.",
    file: ".pre-commit-config.yaml",
    command: [
      "repos:",
      "  - repo: https://github.com/satwiksps/testseal",
      "    rev: " + RELEASE_REF,
      "    hooks:",
      "      - id: testseal",
    ].join("\n"),
  },
  {
    name: "GitHub Actions",
    title: "Annotate the pull request",
    description: "Install bundled source and annotate the exact changed lines.",
    file: ".github/workflows/testseal.yml",
    command: actionWorkflow,
  },
] as const;

const installCommand = [
  "python -m pip install testseal",
  "testseal demo",
].join("\n");

const ruleReferenceUrl = DOCUMENTATION_URL + "en/latest/rules/";
const architectureUrl = DOCUMENTATION_URL + "en/latest/architecture/";
const securityUrl = REPOSITORY_URL + "/blob/main/SECURITY.md";
const contributingUrl = REPOSITORY_URL + "/blob/main/CONTRIBUTING.md";

export default function Home() {
  const siteUrl = getSiteUrl();
  const externalLinkProps = {
    target: "_blank" as const,
    rel: "noreferrer",
  };
  const schema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "TestSeal",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Cross-platform",
    url: siteUrl,
    license: "https://www.apache.org/licenses/LICENSE-2.0",
    codeRepository: REPOSITORY_URL,
    softwareVersion: RELEASE_VERSION,
    description:
      "Deterministic test-integrity checks for Python and pytest diffs.",
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#09090b] text-zinc-100">
      <a
        className="fixed left-4 top-4 z-[100] -translate-y-24 rounded-md bg-white px-4 py-2 text-sm font-semibold text-zinc-950 transition-transform focus:translate-y-0"
        href="#main"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#09090b]/90 backdrop-blur-xl">
        <nav
          className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-6 lg:px-8"
          aria-label="Main navigation"
        >
          <a className="flex items-center gap-2.5 font-semibold tracking-tight" href="#top">
            <span
              className="grid size-7 place-items-center rounded-md border border-white/15 bg-white/[0.04] font-mono text-[10px] font-bold text-blue-300"
              aria-hidden="true"
            >
              TS
            </span>
            <span>TestSeal</span>
            <span className="hidden font-mono text-[10px] font-medium text-zinc-400 sm:inline">
              {RELEASE_REF}
            </span>
          </a>

          <div className="hidden items-center gap-7 text-sm text-zinc-400 md:flex">
            <a className="transition-colors hover:text-white" href="#product">
              Product
            </a>
            <a className="transition-colors hover:text-white" href="#checks">
              Checks
            </a>
            <a className="transition-colors hover:text-white" href="#integrations">
              Integrations
            </a>
            <a
              className="transition-colors hover:text-white"
              href={DOCUMENTATION_URL}
              {...externalLinkProps}
            >
              Docs
            </a>
          </div>

          <div className="flex items-center gap-2">
            <a
              className="hidden h-9 items-center rounded-md border border-white/10 bg-white/[0.035] px-3.5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/20 hover:bg-white/[0.07] sm:inline-flex"
              href={REPOSITORY_URL}
              {...externalLinkProps}
            >
              GitHub
            </a>
            <MobileMenu />
          </div>
        </nav>
      </header>

      <main id="main">
        <section id="top" className="relative">
          <div className="hero-grid absolute inset-x-0 top-0 h-[720px] opacity-60" aria-hidden="true" />
          <div className="relative mx-auto max-w-7xl px-5 pb-16 pt-24 sm:px-6 sm:pt-28 lg:px-8 lg:pb-20 lg:pt-32">
            <div className="mx-auto max-w-4xl text-center">
              <p className="mb-5 font-mono text-xs font-medium uppercase tracking-[0.18em] text-blue-300">
                Open source, Python and pytest, runs locally
              </p>
              <h1 className="text-balance text-5xl font-semibold tracking-[-0.045em] text-white sm:text-6xl lg:text-[72px] lg:leading-[1.04]">
                Catch test weakening
                <span className="block text-zinc-400">before it merges.</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-pretty text-base leading-7 text-zinc-400 sm:text-lg sm:leading-8">
                TestSeal compares the before and after syntax of Python tests and
                flags removed assertions, new skips, wider tolerances, and other
                changes that make a green suite less meaningful.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <a
                  className="inline-flex h-11 w-full items-center justify-center rounded-md bg-white px-5 text-sm font-semibold text-zinc-950 transition-colors hover:bg-zinc-200 sm:w-auto"
                  href="#get-started"
                >
                  Get started
                </a>
                <a
                  className="inline-flex h-11 w-full items-center justify-center rounded-md border border-white/12 bg-white/[0.035] px-5 text-sm font-medium text-zinc-200 transition-colors hover:border-white/20 hover:bg-white/[0.07] sm:w-auto"
                  href={REPOSITORY_URL}
                  {...externalLinkProps}
                >
                  View source
                </a>
              </div>
              <p className="mt-5 text-sm text-zinc-400">
                Deterministic and offline. No LLM, API key, telemetry, or project-code execution.
              </p>
            </div>

            <div id="product" className="mt-14 scroll-mt-24 lg:mt-16">
              <figure
                className="overflow-hidden rounded-xl border border-white/10 bg-[#0c0c0f] shadow-[0_32px_100px_rgba(0,0,0,0.55)]"
              >
                <figcaption className="sr-only">Example TestSeal pull request report</figcaption>
                <div className="flex h-12 items-center justify-between border-b border-white/[0.07] bg-[#111114] px-4 sm:px-5">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="grid size-6 shrink-0 place-items-center rounded border border-white/10 bg-white/[0.03] font-mono text-[9px] font-bold text-blue-300">
                      TS
                    </span>
                    <span className="truncate text-xs font-medium text-zinc-300">
                      Pull request report
                    </span>
                    <span className="hidden text-xs text-zinc-400 sm:inline">/</span>
                    <span className="hidden font-mono text-[11px] text-zinc-400 sm:inline">
                      examples/diffs/assertion-weakened.diff
                    </span>
                  </div>
                  <span className="flex shrink-0 items-center gap-2 font-mono text-[10px] text-emerald-300">
                    <i className="size-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
                    SCAN COMPLETE
                  </span>
                </div>

                <div className="grid lg:grid-cols-[minmax(0,1fr)_360px]">
                  <div className="min-w-0">
                    <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 sm:px-5">
                      <span className="font-mono text-[11px] text-zinc-400">
                        tests/test_totals.py
                      </span>
                      <span className="font-mono text-[10px] text-zinc-400">2 lines changed</span>
                    </div>

                    <div className="overflow-x-auto py-5 font-mono text-[11px] leading-7 sm:py-7 sm:text-[13px]">
                      <div className="grid min-w-[590px] grid-cols-[44px_24px_1fr] border-y border-blue-400/10 bg-blue-400/[0.025] px-3 text-zinc-400 sm:px-5">
                        <span>8</span>
                        <span />
                        <code>    order = Order(items=[Item(price=Decimal(&quot;19.99&quot;))])</code>
                      </div>
                      <div className="grid min-w-[590px] grid-cols-[44px_24px_1fr] px-3 text-zinc-400 sm:px-5">
                        <span>9</span>
                        <span />
                        <code>    total = calculate_total(order)</code>
                      </div>
                      <div className="grid min-w-[590px] grid-cols-[44px_24px_1fr] border-y border-rose-400/10 bg-rose-400/[0.06] px-3 text-rose-200 sm:px-5">
                        <span className="text-zinc-400">10</span>
                        <span className="text-rose-400">−</span>
                        <code>    assert total == Decimal(&quot;19.99&quot;)</code>
                      </div>
                      <div className="grid min-w-[590px] grid-cols-[44px_24px_1fr] border-b border-emerald-400/10 bg-emerald-400/[0.055] px-3 text-emerald-200 sm:px-5">
                        <span className="text-zinc-400">10</span>
                        <span className="text-emerald-400">+</span>
                        <code>    assert total</code>
                      </div>
                    </div>

                    <div className="border-t border-white/[0.07] bg-black/20 px-4 py-4 font-mono text-[11px] sm:px-5 sm:text-xs">
                      <div className="flex gap-3">
                        <span className="select-none text-blue-300">$</span>
                        <code className="text-zinc-300">
                          testseal scan --diff examples/diffs/assertion-weakened.diff
                        </code>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-zinc-400">
                        <span><b className="font-medium text-rose-300">1 high</b> finding</span>
                        <span>advisory mode</span>
                        <span>JSON and SARIF available</span>
                      </div>
                    </div>
                  </div>

                  <aside className="border-t border-white/[0.07] bg-[#0a0a0d] lg:border-l lg:border-t-0">
                    <div className="flex h-12 items-center justify-between border-b border-white/[0.07] px-5">
                      <span className="text-xs font-medium text-zinc-300">Review findings</span>
                      <span className="grid size-5 place-items-center rounded bg-white/[0.06] font-mono text-[10px] text-zinc-400">
                        1
                      </span>
                    </div>
                    <div className="p-5">
                      <div className="flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-wider">
                        <span className="text-rose-300">High</span>
                        <span className="text-zinc-700">/</span>
                        <span className="text-blue-300">TS003</span>
                      </div>
                      <p className="mt-4 text-base font-semibold text-white">Assertion weakened</p>
                      <p className="mt-2 text-sm leading-6 text-zinc-400">
                        A specific equality assertion was replaced by a truthy/non-null check.
                      </p>

                      <div className="mt-5 rounded-md border border-white/[0.07] bg-black/20">
                        <div className="border-b border-white/[0.06] px-3 py-2 font-mono text-[9px] uppercase tracking-wider text-zinc-400">
                          Evidence
                        </div>
                        <div className="space-y-2 px-3 py-3 font-mono text-[10px]">
                          <code className="block truncate text-rose-300">assert total == Decimal(&quot;19.99&quot;)</code>
                          <code className="block truncate text-emerald-300">assert total</code>
                        </div>
                      </div>

                      <div className="mt-5 border-l-2 border-blue-400/50 pl-3">
                        <span className="font-mono text-[9px] uppercase tracking-wider text-zinc-400">
                          Review
                        </span>
                        <p className="mt-1.5 text-xs leading-5 text-zinc-400">
                          Assert the specific expected value, type, relationship, or exception.
                        </p>
                      </div>
                    </div>
                  </aside>
                </div>
              </figure>
            </div>

            <div className="grid gap-px border-x border-b border-white/[0.07] bg-white/[0.07] sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["AST-aware", "before / after analysis"],
                ["Offline", "no network boundary"],
                ["Portable", "text / JSON / SARIF"],
                ["Consistent", "CLI / hook / Action"],
              ].map(([label, detail]) => (
                <div
                  className="bg-[#0b0b0e] px-5 py-4"
                  key={label}
                >
                  <strong className="block text-xs font-medium text-zinc-200">{label}</strong>
                  <span className="mt-1 block font-mono text-[10px] text-zinc-400">{detail}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y border-white/[0.07] bg-white/[0.012]">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:gap-24 lg:px-8 lg:py-28">
            <div>
              <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                The gap in ordinary CI
              </p>
              <h2 className="mt-4 max-w-xl text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                A green build can outlive the guarantee it was meant to enforce.
              </h2>
            </div>
            <div className="space-y-8 text-base leading-7 text-zinc-400">
              <p>
                Both sides of a weakened assertion can be valid Python. Linters stay quiet,
                tests stay green, and the semantic downgrade gets buried inside the diff.
              </p>
              <dl className="divide-y divide-white/[0.07] border-y border-white/[0.07]">
                <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]">
                  <dt className="text-sm font-medium text-zinc-200">Ordinary CI</dt>
                  <dd className="text-sm text-zinc-400">Did the current suite pass?</dd>
                </div>
                <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]">
                  <dt className="text-sm font-medium text-zinc-200">TestSeal</dt>
                  <dd className="text-sm text-zinc-400">Did the suite become easier to pass?</dd>
                </div>
              </dl>
              <p className="text-sm text-zinc-400">
                TestSeal reports the observed transformation. It does not infer intent,
                authorship, or whether AI wrote the change.
              </p>
            </div>
          </div>
        </section>

        <section id="checks" className="scroll-mt-24">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-6 lg:grid-cols-[1fr_420px] lg:items-end">
              <div>
                <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                  Eight deterministic checks
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Focused on test integrity.
                </h2>
              </div>
              <p className="text-sm leading-6 text-zinc-400">
                Every rule describes a concrete before-and-after transformation.
                Context-heavy signals remain lower severity and advisory.
              </p>
            </div>

            <div className="mt-10 overflow-hidden rounded-lg border border-white/[0.08]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-left">
                  <thead className="bg-white/[0.025] font-mono text-[10px] uppercase tracking-[0.12em] text-zinc-400">
                    <tr>
                      <th className="w-28 px-5 py-3 font-medium">Rule</th>
                      <th className="w-56 px-5 py-3 font-medium">Signal</th>
                      <th className="px-5 py-3 font-medium">What changed</th>
                      <th className="w-28 px-5 py-3 font-medium">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.07]">
                    {rules.map((rule) => (
                      <tr className="bg-[#0b0b0e] transition-colors hover:bg-white/[0.025]" key={rule.id}>
                        <td className="px-5 py-4 font-mono text-xs font-semibold text-blue-300">{rule.id}</td>
                        <td className="px-5 py-4 text-sm font-medium text-zinc-200">{rule.title}</td>
                        <td className="px-5 py-4 text-sm text-zinc-400">{rule.description}</td>
                        <td className={"px-5 py-4 font-mono text-[10px] font-semibold uppercase " + severityStyles[rule.severity]}>
                          {rule.severity}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <a
              className="mt-5 inline-flex text-sm font-medium text-zinc-400 transition-colors hover:text-white"
              href={ruleReferenceUrl}
              {...externalLinkProps}
            >
              Supported patterns and limits
            </a>
          </div>
        </section>

        <section id="integrations" className="scroll-mt-24 border-y border-white/[0.07] bg-white/[0.012]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="max-w-2xl">
              <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                One engine, three review surfaces
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                Run it where the change happens.
              </h2>
              <p className="mt-4 text-base leading-7 text-zinc-400">
                The Python analyzer owns every finding. Local scans and CI annotations
                stay consistent because there is no second detection engine.
              </p>
            </div>

            <div className="mt-10 grid overflow-hidden rounded-lg border border-white/[0.08] lg:grid-cols-3">
              {integrations.map((integration) => (
                <article className="border-b border-white/[0.08] bg-[#0b0b0e] p-5 last:border-b-0 lg:border-b-0 lg:border-r lg:last:border-r-0" key={integration.name}>
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-blue-300">
                    {integration.name}
                  </span>
                  <h3 className="mt-3 text-base font-semibold text-zinc-100">{integration.title}</h3>
                  <p className="mt-2 min-h-12 text-sm leading-6 text-zinc-400">{integration.description}</p>
                  <div className="mt-5 overflow-hidden rounded-md border border-white/[0.07] bg-black/25">
                    <div className="flex h-9 items-center justify-between border-b border-white/[0.06] px-3">
                      <span className="truncate font-mono text-[10px] text-zinc-400">{integration.file}</span>
                      <CopyButton value={integration.command} label={"Copy " + integration.name + " example"} />
                    </div>
                    <pre className="min-h-24 overflow-x-auto p-3 font-mono text-[11px] leading-5 text-zinc-400">
                      <code>{integration.command}</code>
                    </pre>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" className="scroll-mt-24">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-12 lg:grid-cols-[0.82fr_1.18fr] lg:gap-24">
              <div>
                <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                  Small, explicit trust boundary
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Inspect the diff. Do not execute it.
                </h2>
                <p className="mt-5 text-base leading-7 text-zinc-400">
                  TestSeal reads Git changes and Python syntax. It never imports the
                  target repository or runs code from the pull request.
                </p>
                <a
                  className="mt-6 inline-flex text-sm font-medium text-zinc-300 transition-colors hover:text-white"
                  href={architectureUrl}
                  {...externalLinkProps}
                >
                  Read the architecture
                </a>
              </div>

              <div>
                <ol className="grid gap-px overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.08] sm:grid-cols-2">
                  {[
                    ["01", "Read the change", "Git refs, staged changes, the working tree, or a unified diff."],
                    ["02", "Hydrate both states", "Recover complete before and after Python source where available."],
                    ["03", "Compare syntax", "Evaluate narrow AST-level transformations with documented limits."],
                    ["04", "Publish evidence", "Return file, line, rule, severity, evidence, and remediation."],
                  ].map(([number, title, description]) => (
                    <li className="bg-[#0b0b0e] p-5" key={number}>
                      <span className="font-mono text-[10px] text-zinc-400">{number}</span>
                      <h3 className="mt-5 text-sm font-semibold text-zinc-200">{title}</h3>
                      <p className="mt-2 text-xs leading-5 text-zinc-400">{description}</p>
                    </li>
                  ))}
                </ol>
                <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-white/[0.07] pt-6 text-xs text-zinc-400 sm:grid-cols-4">
                  {["No imports", "No test runs", "No model calls", "No telemetry"].map((fact) => (
                    <span className="flex items-center gap-2" key={fact}>
                      <i className="size-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
                      {fact}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="get-started" className="scroll-mt-24 border-t border-white/[0.07]">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-6 lg:px-8 lg:py-28">
            <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center lg:gap-20">
              <div>
                <p className="font-mono text-xs font-medium uppercase tracking-[0.16em] text-blue-300">
                  Install the release
                </p>
                <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-white sm:text-4xl">
                  Add a second signal to your next Python review.
                </h2>
                <p className="mt-4 text-sm leading-6 text-zinc-400">
                  Install v{RELEASE_VERSION}, evaluate findings in advisory mode, and opt
                  into blocking after measuring your baseline.
                </p>
              </div>
              <div className="overflow-hidden rounded-lg border border-white/[0.09] bg-[#0b0b0e]">
                <div className="flex h-11 items-center justify-between border-b border-white/[0.07] px-4">
                  <span className="font-mono text-[10px] text-zinc-400">terminal</span>
                  <CopyButton value={installCommand} label="Copy installation commands" />
                </div>
                <pre className="overflow-x-auto p-4 font-mono text-[11px] leading-6 text-zinc-300 sm:p-5 sm:text-xs">
                  <code>{installCommand}</code>
                </pre>
              </div>
            </div>

            <div className="mt-14 flex flex-col gap-4 border-t border-white/[0.07] pt-8 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-zinc-400">
                Apache-2.0, Python 3.11+, advisory by default
              </p>
              <a
                className="inline-flex h-10 items-center justify-center rounded-md bg-white px-4 text-sm font-semibold text-zinc-950 transition-colors hover:bg-zinc-200"
                href={PYPI_URL}
                {...externalLinkProps}
              >
                View on PyPI
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.07] bg-[#070708]">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-10 sm:px-6 md:flex-row md:items-end md:justify-between lg:px-8">
          <div>
            <a className="inline-flex items-center gap-2.5 font-semibold tracking-tight" href="#top">
              <span className="grid size-7 place-items-center rounded-md border border-white/15 bg-white/[0.04] font-mono text-[10px] font-bold text-blue-300" aria-hidden="true">
                TS
              </span>
              TestSeal
            </a>
            <p className="mt-3 max-w-sm text-xs leading-5 text-zinc-400">
              Deterministic test-integrity checks for Python and pytest diffs.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-xs text-zinc-400">
            <a className="hover:text-zinc-200" href={DOCUMENTATION_URL} {...externalLinkProps}>Docs</a>
            <a className="hover:text-zinc-200" href={ruleReferenceUrl} {...externalLinkProps}>Rules</a>
            <a className="hover:text-zinc-200" href={securityUrl} {...externalLinkProps}>Security</a>
            <a className="hover:text-zinc-200" href={contributingUrl} {...externalLinkProps}>Contributing</a>
            <a className="hover:text-zinc-200" href={PYPI_URL} {...externalLinkProps}>PyPI</a>
            <a className="hover:text-zinc-200" href={REPOSITORY_URL} {...externalLinkProps}>GitHub</a>
          </div>
        </div>
        <div className="mx-auto flex max-w-7xl flex-col gap-1 border-t border-white/[0.05] px-5 py-5 font-mono text-[11px] text-zinc-400 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <span>Apache License 2.0</span>
          <span>{RELEASE_REF}, deterministic and offline</span>
        </div>
      </footer>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(schema).replace(/</g, "\\u003c"),
        }}
      />
    </div>
  );
}
