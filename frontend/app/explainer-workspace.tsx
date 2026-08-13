"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileText,
  Gauge,
  Globe2,
  ImageUp,
  Link2,
  Loader2,
  Newspaper,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import type {
  AnalyticalLens,
  ExplanationDepth,
  ExplanationResponse,
  InputType,
  StreamEvent,
  UserInputRequest,
} from "@/types/api-contracts";
import { streamExplanation } from "@/lib/explain-stream";

type InputModeOption = {
  label: string;
  value: InputType;
};

type LensOption = {
  label: string;
  value: AnalyticalLens;
};

type WorkflowState = "empty" | "loading" | "success" | "error";

const inputModes: InputModeOption[] = [
  { label: "Topik", value: "topic" },
  { label: "Pertanyaan", value: "question" },
  { label: "Headline", value: "headline" },
  { label: "Teks", value: "text" },
  { label: "URL", value: "url" },
  { label: "Screenshot", value: "screenshot" },
];

const lenses: LensOption[] = [
  { label: "Keuangan", value: "personal_finances" },
  { label: "Pajak", value: "taxes" },
  { label: "Pekerjaan", value: "jobs" },
  { label: "Pendidikan", value: "education" },
  { label: "Lingkungan", value: "environment" },
  { label: "Kebebasan sipil", value: "civil_liberties" },
  { label: "Demokrasi", value: "democracy" },
  { label: "Layanan publik", value: "public_services" },
  { label: "Dampak daerah", value: "regional_impact" },
];

function createRequest(
  inputType: InputType,
  text: string,
  url: string,
  depth: ExplanationDepth,
  selectedLenses: AnalyticalLens[],
): UserInputRequest {
  return {
    input_type: inputType,
    text: inputType === "url" ? null : text.trim(),
    url: inputType === "url" ? url.trim() : null,
    image_id: inputType === "screenshot" ? "local-upload-placeholder" : null,
    depth,
    lenses: selectedLenses,
    locale: "id-ID",
  };
}

export function ExplainerWorkspace() {
  const [inputType, setInputType] = useState<InputType>("question");
  const [text, setText] = useState("Kenapa mahasiswa protes revisi UU TNI?");
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState<ExplanationDepth>("quick");
  const [selectedLenses, setSelectedLenses] = useState<AnalyticalLens[]>(["democracy"]);
  const [workflowState, setWorkflowState] = useState<WorkflowState>("empty");
  const [lastRequest, setLastRequest] = useState<UserInputRequest | null>(null);
  const [progressEvents, setProgressEvents] = useState<StreamEvent[]>([]);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isUrlMode = inputType === "url";
  const isScreenshotMode = inputType === "screenshot";
  const canSubmit = isUrlMode ? url.trim().length > 0 : text.trim().length > 0;

  const statusLabel = useMemo(() => {
    if (workflowState === "loading") return "Streaming";
    if (workflowState === "success") return "Answer ready";
    if (workflowState === "error") return "Needs input";
    return "Ready";
  }, [workflowState]);

  function toggleLens(lens: AnalyticalLens) {
    setSelectedLenses((current) =>
      current.includes(lens) ? current.filter((item) => item !== lens) : [...current, lens],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!canSubmit) {
      setErrorMessage("Add a question, text, or URL before asking Politik Yuk to explain it.");
      setWorkflowState("error");
      return;
    }

    const request = createRequest(inputType, text, url, depth, selectedLenses);
    setLastRequest(request);
    setProgressEvents([]);
    setExplanation(null);
    setErrorMessage(null);
    setWorkflowState("loading");

    try {
      await streamExplanation(request, (update) => {
        setProgressEvents((current) => [...current, update.event]);
        if (update.type === "complete") {
          setExplanation(update.explanation);
          setWorkflowState("success");
        }
        if (update.type === "error") {
          const message =
            typeof update.event.payload.error === "string"
              ? update.event.payload.error
              : update.event.message;
          setErrorMessage(message);
          setWorkflowState("error");
        }
      });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Explain request failed.");
      setWorkflowState("error");
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-ink/15 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-civic">
              Politik Yuk
            </p>
            <h1 className="mt-2 max-w-4xl text-3xl font-semibold sm:text-5xl">
              Understand political news with sources, uncertainty, and context in view.
            </h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-ink/70">
            <ShieldCheck aria-hidden="true" className="h-5 w-5 text-civic" />
            <span>Facts stay grounded; depth adapts.</span>
          </div>
        </header>

        <div className="grid flex-1 gap-5 lg:grid-cols-[minmax(340px,0.85fr)_minmax(0,1.15fr)]">
          <form
            className="rounded-lg border border-ink/15 bg-white p-5 shadow-sm"
            onSubmit={handleSubmit}
          >
            <div className="flex items-center gap-2">
              <Search aria-hidden="true" className="h-5 w-5 text-civic" />
              <h2 className="text-xl font-semibold">Ask for context</h2>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3" aria-label="Input modes">
              {inputModes.map((mode) => {
                const isActive = inputType === mode.value;
                return (
                  <button
                    aria-pressed={isActive}
                    className={[
                      "rounded-md border px-3 py-2 text-sm font-medium transition",
                      isActive
                        ? "border-civic bg-civic text-white"
                        : "border-ink/15 text-ink/80 hover:border-civic hover:text-civic",
                    ].join(" ")}
                    key={mode.value}
                    onClick={() => setInputType(mode.value)}
                    type="button"
                  >
                    {mode.label}
                  </button>
                );
              })}
            </div>

            <label className="mt-5 block text-sm font-medium" htmlFor="political-input">
              Topic, question, headline, pasted claim, or social text
            </label>
            <textarea
              className="mt-2 min-h-40 w-full resize-y rounded-md border border-ink/20 bg-paper/50 p-3 text-base outline-none transition focus:border-civic focus:ring-2 focus:ring-civic/20 disabled:cursor-not-allowed disabled:bg-ink/5"
              disabled={isUrlMode}
              id="political-input"
              onChange={(event) => setText(event.target.value)}
              placeholder="Contoh: Kenapa revisi UU TNI diprotes mahasiswa?"
              value={text}
            />

            <label className="mt-4 block text-sm font-medium" htmlFor="source-url">
              URL source
            </label>
            <div className="mt-2 flex items-center gap-2 rounded-md border border-ink/20 bg-paper/50 px-3 py-2 focus-within:border-civic focus-within:ring-2 focus-within:ring-civic/20">
              <Link2 aria-hidden="true" className="h-4 w-4 text-ink/50" />
              <input
                className="w-full bg-transparent outline-none disabled:cursor-not-allowed"
                disabled={!isUrlMode}
                id="source-url"
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://..."
                type="url"
                value={url}
              />
            </div>

            <div className="mt-4 rounded-md border border-dashed border-ink/20 p-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <ImageUp aria-hidden="true" className="h-4 w-4 text-civic" />
                Screenshot upload
              </div>
              <input
                accept="image/png,image/jpeg,image/webp"
                aria-label="Screenshot upload"
                className="mt-3 block w-full text-sm"
                disabled={!isScreenshotMode}
                type="file"
              />
              <p className="mt-2 text-xs leading-5 text-ink/60">
                Screenshot text is treated as an unverified claim to investigate.
              </p>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
              <label className="block text-sm font-medium" htmlFor="depth">
                Depth
                <select
                  className="mt-2 w-full rounded-md border border-ink/20 bg-white p-3"
                  id="depth"
                  onChange={(event) => setDepth(event.target.value as ExplanationDepth)}
                  value={depth}
                >
                  <option value="quick">Quick Read</option>
                  <option value="in_depth">In Depth</option>
                </select>
              </label>

              <fieldset>
                <legend className="text-sm font-medium">Analytical lens</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {lenses.map((lens) => (
                    <label
                      className="flex items-center gap-2 rounded-md border border-ink/15 px-3 py-2 text-sm"
                      key={lens.value}
                    >
                      <input
                        checked={selectedLenses.includes(lens.value)}
                        className="h-4 w-4 accent-civic"
                        onChange={() => toggleLens(lens.value)}
                        type="checkbox"
                      />
                      {lens.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            {workflowState === "error" ? (
              <div className="mt-4 flex items-start gap-2 rounded-md border border-signal/30 bg-signal/10 p-3 text-sm text-signal">
                <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4" />
                {errorMessage ?? "Explain request failed."}
              </div>
            ) : null}

            <button
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-civic px-4 py-3 font-semibold text-white transition hover:bg-civic/90 disabled:cursor-not-allowed disabled:bg-ink/30"
              disabled={workflowState === "loading"}
              type="submit"
            >
              {workflowState === "loading" ? (
                <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
              ) : (
                <FileText aria-hidden="true" className="h-5 w-5" />
              )}
              Explain with sources
            </button>
          </form>

          <section className="rounded-lg border border-ink/15 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 border-b border-ink/10 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <Newspaper aria-hidden="true" className="h-5 w-5 text-signal" />
                <h2 className="text-xl font-semibold">Structured answer</h2>
              </div>
              <div className="flex items-center gap-2 rounded-md bg-field px-3 py-2 text-sm">
                {workflowState === "loading" ? (
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <Gauge aria-hidden="true" className="h-4 w-4" />
                )}
                {statusLabel}
              </div>
            </div>

            <div className="mt-5 grid gap-4">
              {workflowState === "empty" ? (
                <div className="rounded-md border border-ink/10 bg-paper/40 p-4">
                  <div className="flex items-center gap-2 font-semibold">
                    <Sparkles aria-hidden="true" className="h-5 w-5 text-civic" />
                    Streaming response surface
                  </div>
                  <p className="mt-2 text-sm leading-6 text-ink/70">
                    Submit the form to stream placeholder graph progress from FastAPI and render
                    the final structured response.
                  </p>
                </div>
              ) : null}

              {workflowState === "loading" ? (
                <div className="grid gap-3">
                  {(progressEvents.length
                    ? progressEvents
                    : [
                        {
                          request_id: "pending",
                          event_type: "request_received" as const,
                          message: "Waiting for backend stream",
                          payload: {},
                        },
                      ]
                  ).map((streamEvent, index) => (
                    <div
                      className="flex items-center gap-3 rounded-md border border-ink/10 p-3 text-sm"
                      key={`${streamEvent.event_type}-${index}`}
                    >
                      <Clock3 aria-hidden="true" className="h-4 w-4 text-civic" />
                      <span>{streamEvent.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              {workflowState === "success" && explanation ? (
                <>
                  <div className="rounded-md border border-civic/25 bg-civic/5 p-4">
                    <div className="flex items-center gap-2 font-semibold text-civic">
                      <CheckCircle2 aria-hidden="true" className="h-5 w-5" />
                      Request preview
                    </div>
                    <p className="mt-2 text-sm leading-6 text-ink/70">
                      Mode: {lastRequest?.input_type}. Depth: {lastRequest?.depth}. Lenses:{" "}
                      {lastRequest?.lenses.length ? lastRequest.lenses.join(", ") : "none"}.
                    </p>
                  </div>

                  {explanation.sections.map((section) => (
                    <article className="rounded-md border border-ink/10 p-4" key={section.title}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="font-semibold">{section.title}</h3>
                        <span className="rounded-md bg-field px-2 py-1 text-xs">
                          uncertainty: {section.uncertainty}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-ink/75">{section.body}</p>
                      {section.citation_ids.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {section.citation_ids.map((citationId) => (
                            <span
                              className="rounded-md border border-civic/30 px-2 py-1 text-xs text-civic"
                              key={citationId}
                            >
                              [{citationId}]
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}

                  <div className="grid gap-4 xl:grid-cols-2">
                    <section className="rounded-md border border-ink/10 p-4">
                      <div className="flex items-center gap-2 font-semibold">
                        <Globe2 aria-hidden="true" className="h-5 w-5 text-civic" />
                        Citations
                      </div>
                      <div className="mt-3 grid gap-3">
                        {explanation.citations.map((citation) => {
                          const source = explanation.sources.find(
                            (item) => item.id === citation.source_id,
                          );
                          return (
                            <div className="rounded-md bg-paper/50 p-3 text-sm" key={citation.id}>
                              <div className="font-semibold">
                                [{citation.label}] {source?.title}
                              </div>
                              <p className="mt-1 text-ink/65">{source?.publisher}</p>
                              <p className="mt-2 leading-5 text-ink/70">{citation.quote}</p>
                            </div>
                          );
                        })}
                      </div>
                    </section>

                    <section className="rounded-md border border-ink/10 p-4">
                      <div className="flex items-center gap-2 font-semibold">
                        <Users aria-hidden="true" className="h-5 w-5 text-civic" />
                        Related entities
                      </div>
                      <div className="mt-3 grid gap-3">
                        {explanation.entities.map((entity) => (
                          <button
                            className="rounded-md border border-ink/10 p-3 text-left text-sm transition hover:border-civic"
                            key={entity.id}
                            type="button"
                          >
                            <span className="font-semibold">{entity.name}</span>
                            <span className="ml-2 text-xs text-ink/50">{entity.entity_type}</span>
                            <p className="mt-2 leading-5 text-ink/70">{entity.description}</p>
                          </button>
                        ))}
                      </div>
                    </section>
                  </div>
                </>
              ) : null}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
