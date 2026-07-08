# Politik Yuk

<<<<<<< HEAD
Paham Politik is a small Indonesian-language political news explainer for young
readers. The MVP will use Cohere Aya to turn dense political news into clear,
neutral, age-aware explanations.

## Current Milestone

Milestone 2 connects the interface to a local API endpoint backed by Cohere Aya:

- Article input form.
- Reading level selector for SMP, SMA, and Mahasiswa.
- `/api/explain` endpoint for generation requests.
- Cohere v2 Chat API integration using `c4ai-aya-expanse-32b`.
- Server-side validation and API error handling.
- Mocked tests for Cohere request payloads and response parsing.

Copy `.env.example` to `.env` or set these environment variables before using
real model calls:

```bash
COHERE_API_KEY=your_cohere_api_key_here
COHERE_MODEL=c4ai-aya-expanse-32b
```
=======
Paham Politik is a small Indonesian-language political news explainer for young readers. The purpose of this project was to test Cohere Aya for fun! 
>>>>>>> main

## Run Locally

```bash
npm start
```

Then open [http://localhost:4173](http://localhost:4173).

## Test

```bash
npm test
```
