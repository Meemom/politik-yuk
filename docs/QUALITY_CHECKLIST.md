# Quality Checklist

Use this checklist before merging the MVP stack or after changing the prompt.

## Automated Checks

Run:

```bash
npm test
```

Expected result:

- All tests pass.
- Prompt tests confirm the Indonesian neutrality and verification guardrails.
- History tests confirm local storage keeps only the newest five explanations.
- Cohere tests confirm the app calls the v2 Chat API with the Aya Expanse model.

## Local Server Smoke Checks

Run:

```bash
npm start
```

Then check:

- `http://127.0.0.1:4173` returns the app shell.
- The article input, reading level controls, result panel, and history panel are visible.
- Submitting fewer than 300 characters returns a validation error.
- Submitting 300 or more characters without `COHERE_API_KEY` returns the missing-key message.

## Manual Aya Checks

Set a real Cohere API key:

```bash
COHERE_API_KEY=your_key npm start
```

For each article, test all three levels: SMP, SMA, and Mahasiswa.

Check that Aya:

- Preserves the article's meaning.
- Does not add unsupported facts.
- Uses simpler language for SMP than Mahasiswa.
- Explains difficult political, legal, or bureaucratic terms.
- Avoids partisan framing.
- Marks claims, numbers, accusations, and predictions as things to verify.
- Produces all eight MVP sections.

## Suggested Article Scenarios

Use real articles only when you have permission or can paste excerpts for private testing. For repeatable local QA, synthetic scenarios are enough:

1. **Election Promise**
   - A candidate promises free school meals, but the article does not explain the budget source.
   - Expected: budget claims should appear in "Hal yang Perlu Dicek Lagi".

2. **DPR Bill Discussion**
   - A commission debates a bill with legal terms such as RUU, pasal, fraksi, and rapat dengar pendapat.
   - Expected: legal and institutional terms should appear in "Istilah Sulit".

3. **Regional Policy**
   - A governor announces a transport fare change with different impacts on students, workers, and small vendors.
   - Expected: daily impacts should be practical but not exaggerated.

4. **Public Budget Debate**
   - Officials debate subsidy changes and cite numbers from different sources.
   - Expected: conflicting numbers should be marked for verification.

5. **Cabinet Announcement**
   - A ministry announces a policy timeline with unclear implementation details.
   - Expected: uncertainty should be separated from confirmed article facts.

## Merge Order

The milestone PRs are stacked. Merge them in order:

1. Milestone 1: static MVP interface.
2. Milestone 2: Aya API integration.
3. Milestone 3: structured output.
4. Milestone 4: local history.
5. Milestone 5: quality pass.
