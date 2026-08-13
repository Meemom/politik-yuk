import React from "react";
import { FileText, Gauge, Newspaper, Search, ShieldCheck } from "lucide-react";

const inputModes = ["Topik", "Pertanyaan", "Headline", "Teks", "URL", "Screenshot"];
const lenses = ["Demokrasi", "Pekerjaan", "Pajak", "Pendidikan", "Lingkungan"];

export default function Home() {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-5 py-6 sm:px-8 lg:px-10">
        <header className="flex flex-col gap-4 border-b border-ink/15 pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.16em] text-civic">
              Political context engine
            </p>
            <h1 className="mt-2 max-w-3xl text-3xl font-semibold sm:text-5xl">
              Understand Indonesian political news with evidence in view.
            </h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-ink/70">
            <ShieldCheck aria-hidden="true" className="h-5 w-5 text-civic" />
            <span>Facts stay grounded; depth adapts.</span>
          </div>
        </header>

        <div className="grid flex-1 gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="rounded-lg border border-ink/15 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <Search aria-hidden="true" className="h-5 w-5 text-civic" />
              <h2 className="text-xl font-semibold">Ask for context</h2>
            </div>

            <div className="mt-5 flex flex-wrap gap-2" aria-label="Input modes">
              {inputModes.map((mode) => (
                <button
                  className="rounded-md border border-ink/15 px-3 py-2 text-sm font-medium text-ink/80 transition hover:border-civic hover:text-civic"
                  key={mode}
                  type="button"
                >
                  {mode}
                </button>
              ))}
            </div>

            <label className="mt-5 block text-sm font-medium" htmlFor="political-input">
              Topic, question, headline, URL, or pasted claim
            </label>
            <textarea
              className="mt-2 min-h-44 w-full resize-y rounded-md border border-ink/20 bg-paper/50 p-3 text-base outline-none transition focus:border-civic focus:ring-2 focus:ring-civic/20"
              id="political-input"
              placeholder="Contoh: Kenapa revisi UU TNI diprotes mahasiswa?"
            />

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium" htmlFor="depth">
                Depth
                <select
                  className="mt-2 w-full rounded-md border border-ink/20 bg-white p-3"
                  defaultValue="quick"
                  id="depth"
                >
                  <option value="quick">Quick Read</option>
                  <option value="deep">In Depth</option>
                </select>
              </label>

              <fieldset>
                <legend className="text-sm font-medium">Analytical lens</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {lenses.map((lens) => (
                    <label
                      className="flex items-center gap-2 rounded-md border border-ink/15 px-3 py-2 text-sm"
                      key={lens}
                    >
                      <input className="h-4 w-4 accent-civic" type="checkbox" />
                      {lens}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            <button
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-civic px-4 py-3 font-semibold text-white transition hover:bg-civic/90"
              type="button"
            >
              <FileText aria-hidden="true" className="h-5 w-5" />
              Explain with sources
            </button>
          </section>

          <section className="rounded-lg border border-ink/15 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Newspaper aria-hidden="true" className="h-5 w-5 text-signal" />
                <h2 className="text-xl font-semibold">Structured answer shell</h2>
              </div>
              <div className="flex items-center gap-2 rounded-md bg-field px-3 py-2 text-sm">
                <Gauge aria-hidden="true" className="h-4 w-4" />
                Ready
              </div>
            </div>

            <div className="mt-6 grid gap-4">
              {[
                ["TL;DR", "A concise source-grounded summary will stream here."],
                ["Essential context", "Background, stakeholders, and timeline hooks."],
                ["Key claims", "Fact, interpretation, prediction, and uncertainty labels."],
                ["Citations", "Claim-level source links with evidence passages."],
              ].map(([title, body]) => (
                <article className="rounded-md border border-ink/10 p-4" key={title}>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-6 text-ink/70">{body}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
