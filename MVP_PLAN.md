# MVP Implementation Plan: Political News Explainer for Young Indonesians

## 1. Product Goal

<<<<<<< HEAD
<<<<<<< HEAD
A small web app that helps young Indonesian users understand complex political news in clear, age-appropriate Bahasa Indonesia.
=======
Build a small web app that helps young Indonesian users understand complex political news in clear, age-appropriate Bahasa Indonesia.
>>>>>>> main

The app should let a user paste a political news article, choose a target reading level, and receive a structured explanation that is easier to understand without changing the article's meaning.
=======
A small web app that helps young Indonesian users understand complex political news in clear, age-appropriate Bahasa Indonesia.
>>>>>>> main

## 2. Target Users

- Indonesian middle school students who need simple explanations of current events.
- Indonesian high school students learning civic literacy and political awareness.
- University students who want faster context before reading deeper.
- Teachers or mentors who want discussion prompts from current news.

## 3. MVP Scope

### In Scope

- Paste Indonesian political news text into a text area.
- Select explanation level:
  - SMP
  - SMA
  - Mahasiswa
- Generate a structured explanation using Cohere Aya.
- Display results in Bahasa Indonesia.
- Include safeguards against overclaiming or unsupported conclusions.
- Provide a basic responsive UI.
- Keep a small local history of generated explanations in the browser.

### Out of Scope

- Automatic article fetching from URLs.
- User accounts.
- Database persistence.
- Fact-checking against external sources.
- Real-time news aggregation.
- Social sharing.
- Mobile app packaging.

## 4. Core User Flow

1. User opens the app.
2. User pastes a political news article or excerpt.
3. User chooses the target reading level.
4. User clicks "Jelaskan".
5. App sends the article, level, and instruction prompt to the backend.
6. Backend calls Cohere Aya.
7. App displays a structured explanation.
8. User can copy the explanation or generate another version.

## 5. Main Output Format

The model response should be structured into these sections:

1. **Ringkasan Singkat**
   - 3 to 5 sentences explaining what happened.

2. **Penjelasan Sederhana**
   - A clearer explanation adapted to the selected reading level.

3. **Tokoh dan Lembaga Penting**
   - People, parties, ministries, agencies, or institutions mentioned.
   - Explain each in plain language.

4. **Istilah Sulit**
   - Political, legal, economic, or bureaucratic terms.
   - Define each term in simple Indonesian.

5. **Kenapa Ini Penting**
   - Explain why the topic matters for society or young people.

6. **Dampak ke Kehidupan Sehari-hari**
   - Explain possible practical effects without exaggerating.

7. **Pertanyaan Kritis**
   - 3 to 5 thoughtful questions users can ask after reading.

8. **Hal yang Perlu Dicek Lagi**
   - Claims, numbers, accusations, or predictions that require verification.

<<<<<<< HEAD
<<<<<<< HEAD
## 6. Prompt Design
=======
## 6. Recommended Tech Stack

### Frontend

- React or Next.js for the web interface.
- Tailwind CSS for quick styling.
- Local storage for simple history.

### Backend

- A small API route or server endpoint that receives:
  - `articleText`
  - `readingLevel`
  - optional `tone`
- Backend calls Cohere's chat or generation API with Aya.

### Model

- Cohere Aya model through Cohere API.
- Start with one model configuration and keep parameters simple.

Suggested initial generation settings:

- Temperature: `0.3` to `0.5`
- Max tokens: enough for a complete structured explanation
- Language: Bahasa Indonesia

## 7. Minimal Architecture

```text
Browser UI
  -> POST /api/explain
      -> Validate input
      -> Build prompt
      -> Call Cohere Aya
      -> Parse or return structured text
  <- Explanation response
Browser UI
  -> Render explanation
  -> Save result to local storage
```

## 8. API Contract

### Request

```json
{
  "articleText": "Isi artikel politik...",
  "readingLevel": "SMA"
}
```

### Response

```json
{
  "explanation": {
    "summary": "...",
    "simpleExplanation": "...",
    "entities": [
      {
        "name": "DPR",
        "description": "..."
      }
    ],
    "terms": [
      {
        "term": "hak angket",
        "definition": "..."
      }
    ],
    "whyItMatters": "...",
    "dailyImpact": "...",
    "criticalQuestions": ["...", "..."],
    "needsVerification": ["...", "..."]
  }
}
```

For the MVP, returning Markdown is acceptable and faster to implement. Structured JSON is better if the UI will render each section separately.

## 9. Prompt Design
>>>>>>> main
=======
## 6. Prompt Design
>>>>>>> main

The prompt should instruct Aya to be clear, neutral, and age-aware.

### Prompt Template

```text
Kamu adalah asisten literasi berita politik untuk anak muda Indonesia.

Tugasmu adalah menjelaskan artikel berita politik berikut dalam Bahasa Indonesia yang jelas, netral, dan sesuai untuk tingkat pembaca: {readingLevel}.

Aturan penting:
- Jangan menambahkan fakta baru yang tidak ada di artikel.
- Jika ada klaim yang belum terbukti, tandai sebagai hal yang perlu dicek lagi.
- Jangan berpihak pada partai, tokoh, atau kelompok politik tertentu.
- Jelaskan istilah politik, hukum, atau pemerintahan dengan bahasa sederhana.
- Hindari bahasa yang menggurui.
- Jangan membuat kesimpulan berlebihan.

Artikel:
{articleText}

Berikan hasil dengan format:
1. Ringkasan Singkat
2. Penjelasan Sederhana
3. Tokoh dan Lembaga Penting
4. Istilah Sulit
5. Kenapa Ini Penting
6. Dampak ke Kehidupan Sehari-hari
7. Pertanyaan Kritis
8. Hal yang Perlu Dicek Lagi
```
<<<<<<< HEAD

<<<<<<< HEAD
## 7. Success Criteria
=======
## 10. UI Requirements

### First Screen

- App title: "Paham Politik"
- Large text area for article input.
- Reading level segmented control:
  - SMP
  - SMA
  - Mahasiswa
- Primary action button: "Jelaskan"
- Loading state while waiting for the model.

### Result Screen

- Structured sections with clear headings.
- Copy button for the full explanation.
- Button to start a new explanation.
- Optional local history sidebar or dropdown.

### Empty and Error States

- Empty input: ask the user to paste an article first.
- Very short input: ask for more article context.
- API error: show a calm message and allow retry.
- Long article: either trim with warning or reject with a helpful limit message.

## 11. Input Validation

- Require at least 300 characters.
- Limit to a practical maximum, such as 12,000 to 20,000 characters.
- Strip obvious empty whitespace.
- Do not send empty or extremely short text to the model.

## 12. Safety and Quality Guardrails

- Make neutrality part of the prompt.
- Ask the model to distinguish article facts from interpretation.
- Ask the model to mark claims that need verification.
- Avoid presenting the app as a fact-checker.
- Include a small UI note: "Penjelasan ini membantu memahami artikel, bukan pengganti verifikasi dari sumber tepercaya."

## 13. Suggested File Structure

```text
src/
  app/
    page.tsx
    api/
      explain/
        route.ts
  components/
    ArticleInput.tsx
    ReadingLevelSelector.tsx
    ExplanationResult.tsx
    HistoryPanel.tsx
  lib/
    cohere.ts
    prompt.ts
    validation.ts
```

If using a simpler Vite React app:

```text
src/
  App.tsx
  components/
  lib/
server/
  explain.ts
```

## 14. Implementation Milestones

### Milestone 1: Static UI

- Build the input form.
- Add reading level selection.
- Add placeholder result cards.
- Add responsive layout.

### Milestone 2: API Integration

- Create the `/api/explain` endpoint.
- Add Cohere API client.
- Store API key in environment variable.
- Send article text and reading level to Aya.

### Milestone 3: Prompt and Output

- Implement the prompt template.
- Return Markdown or JSON.
- Render the generated result.
- Add loading and error states.

### Milestone 4: Local History

- Save the last 5 explanations in local storage.
- Allow users to reopen prior results.
- Add clear history action.

### Milestone 5: Quality Pass

- Test with short, medium, and long Indonesian news articles.
- Test SMP, SMA, and Mahasiswa output differences.
- Check whether explanations remain neutral.
- Check whether unsupported claims are flagged.

## 15. Test Articles to Try

Use articles covering different political topics:

- Election campaign promises.
- DPR law discussions.
- Cabinet or ministry policy announcements.
- Regional government issues.
- Public budget or subsidy debates.

For each article, compare:

- Does the summary preserve the original meaning?
- Are difficult terms explained correctly?
- Is the tone appropriate for the chosen reading level?
- Does the model avoid partisan framing?
- Does it clearly identify things that need verification?

## 16. Success Criteria
>>>>>>> main

The MVP is successful if:

- A user can paste an Indonesian political news article and receive an explanation.
- The explanation is easier to understand than the original article.
- The output changes appropriately between SMP, SMA, and Mahasiswa levels.
- The app avoids claiming to verify facts it has not checked.
- The UI is simple enough for a first-time user to understand immediately.

<<<<<<< HEAD
## 8. Future Enhancements
=======
## 17. Future Enhancements
>>>>>>> main

- URL article import.
- Retrieval from trusted Indonesian news sources.
- Fact-check integration with trusted public sources.
- Comparison of multiple articles about the same issue.
- Bias and framing analysis.
- Vocabulary quiz mode for students.
- Teacher worksheet export.
- Support for regional languages or mixed Indonesian slang.
<<<<<<< HEAD
=======

## 18. Recommended MVP Build Order

1. Build the text input and reading level selector.
2. Add a fake response to finalize UI layout.
3. Add the backend API route.
4. Connect Cohere Aya.
5. Tune the prompt with 5 to 10 real Indonesian articles.
6. Add local history.
7. Polish error states and mobile layout.

>>>>>>> main
=======
>>>>>>> main
