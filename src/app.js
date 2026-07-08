import {
  DEFAULT_READING_LEVEL,
  READING_LEVELS,
  buildPlaceholderExplanation,
  validateArticleText,
} from "./explainer.js";

const form = document.querySelector("#explainer-form");
const articleText = document.querySelector("#article-text");
const levelsContainer = document.querySelector("#reading-levels");
const resultContent = document.querySelector("#result-content");
const formMessage = document.querySelector("#form-message");
const copyResultButton = document.querySelector("#copy-result");

let selectedLevel = DEFAULT_READING_LEVEL;
let latestExplanationText = "";

function renderReadingLevels() {
  levelsContainer.replaceChildren(
    ...READING_LEVELS.map((level) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "level-button";
      button.dataset.level = level.id;
      button.setAttribute("aria-pressed", String(level.id === selectedLevel));
      button.innerHTML = `
        <span>${level.label}</span>
        <small>${level.description}</small>
      `;

      button.addEventListener("click", () => {
        selectedLevel = level.id;
        renderReadingLevels();
        renderExplanation();
      });

      return button;
    })
  );
}

function renderExplanation() {
  const sections = buildPlaceholderExplanation(selectedLevel);
  latestExplanationText = sections
    .map((section) => `${section.title}\n${section.body}`)
    .join("\n\n");

  resultContent.replaceChildren(
    ...sections.map((section) => {
      const article = document.createElement("article");
      article.className = "result-section";
      article.innerHTML = `
        <h3>${section.title}</h3>
        <p>${section.body}</p>
      `;
      return article;
    })
  );
}

function renderGeneratedExplanation(explanation) {
  if (typeof explanation === "string") {
    latestExplanationText = explanation;

    const article = document.createElement("article");
    article.className = "result-section generated-result";

    const heading = document.createElement("h3");
    heading.textContent = "Hasil dari Aya";

    const body = document.createElement("pre");
    body.textContent = explanation;

    article.append(heading, body);
    resultContent.replaceChildren(article);
    return;
  }

  const sections = [
    ["Ringkasan Singkat", explanation.summary],
    ["Penjelasan Sederhana", explanation.simpleExplanation],
    ["Tokoh dan Lembaga Penting", formatNamedItems(explanation.entities)],
    ["Istilah Sulit", formatNamedItems(explanation.terms, "term", "definition")],
    ["Kenapa Ini Penting", explanation.whyItMatters],
    ["Dampak ke Kehidupan Sehari-hari", explanation.dailyImpact],
    ["Pertanyaan Kritis", formatList(explanation.criticalQuestions)],
    ["Hal yang Perlu Dicek Lagi", formatList(explanation.needsVerification)],
  ];

  latestExplanationText = sections
    .map(([title, body]) => `${title}\n${body}`)
    .join("\n\n");

  resultContent.replaceChildren(
    ...sections.map(([title, body]) => {
      const article = document.createElement("article");
      article.className = "result-section";

      const heading = document.createElement("h3");
      heading.textContent = title;

      const paragraph = document.createElement("p");
      paragraph.textContent = body || "Tidak disebutkan di artikel.";

      article.append(heading, paragraph);
      return article;
    })
  );
}

function formatList(items = []) {
  return items.length
    ? items.map((item, index) => `${index + 1}. ${item}`).join("\n")
    : "";
}

function formatNamedItems(items = [], nameKey = "name", descriptionKey = "description") {
  return items.length
    ? items
        .map((item) => {
          const name = item[nameKey] ?? "";
          const description = item[descriptionKey] ?? "";
          return description ? `${name}: ${description}` : name;
        })
        .join("\n")
    : "";
}

function setMessage(message) {
  formMessage.textContent = message;
}

function getResultText() {
  return latestExplanationText;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const validationMessage = validateArticleText(articleText.value);

  if (validationMessage) {
    setMessage(validationMessage);
    articleText.focus();
    return;
  }

  setMessage("Membuat penjelasan dengan Aya...");

  try {
    const response = await fetch("/api/explain", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        articleText: articleText.value,
        readingLevel: selectedLevel,
      }),
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error ?? "Gagal membuat penjelasan.");
    }

    renderGeneratedExplanation(payload.explanation);
    setMessage("Penjelasan selesai dibuat.");
  } catch (error) {
    setMessage(error.message);
  }
});

copyResultButton.addEventListener("click", async () => {
  const text = getResultText();

  if (!navigator.clipboard) {
    setMessage("Browser ini belum mendukung salin otomatis.");
    return;
  }

  await navigator.clipboard.writeText(text);
  setMessage("Penjelasan disalin.");
});

renderReadingLevels();
renderExplanation();
