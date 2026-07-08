# MVP Implementation Plan: Political News Explainer for Young Indonesians

## 1. Product Goal

A small web app that helps young Indonesian users understand complex political news in clear, age-appropriate Bahasa Indonesia.

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


## 6. Success Criteria

The MVP is successful if:

- A user can paste an Indonesian political news article and receive an explanation.
- The explanation is easier to understand than the original article.
- The output changes appropriately between SMP, SMA, and Mahasiswa levels.
- The app avoids claiming to verify facts it has not checked.
- The UI is simple enough for a first-time user to understand immediately.

## 7. Future Enhancements

- URL article import.
- Retrieval from trusted Indonesian news sources.
- Fact-check integration with trusted public sources.
- Comparison of multiple articles about the same issue.
- Bias and framing analysis.
- Vocabulary quiz mode for students.
- Teacher worksheet export.
- Support for regional languages or mixed Indonesian slang.

