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

function setMessage(message) {
  formMessage.textContent = message;
}

function getResultText() {
  return Array.from(resultContent.querySelectorAll(".result-section"))
    .map((section) => {
      const title = section.querySelector("h3")?.textContent ?? "";
      const body = section.querySelector("p")?.textContent ?? "";
      return `${title}\n${body}`;
    })
    .join("\n\n");
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const validationMessage = validateArticleText(articleText.value);

  if (validationMessage) {
    setMessage(validationMessage);
    articleText.focus();
    return;
  }

  renderExplanation();
  setMessage(
    "Untuk Milestone 1, hasil ini masih pratinjau statis. Integrasi Aya masuk di Milestone 2."
  );
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
