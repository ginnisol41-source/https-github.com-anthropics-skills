---
name: free-llm-apis
description: Call free-tier LLM APIs (Groq, OpenRouter, Kilo Code, OVHcloud, Gemini, Cohere, NVIDIA NIM, Cloudflare and others from the awesome-free-llm-apis list) to get a second opinion, compare models, delegate cheap bulk text tasks, or test a prompt on open-weight models. Use when the user asks to query, compare or use another LLM or a free model, or names one of these providers.
---

# Free LLM APIs

`scripts/llm.py` sends chat requests to the OpenAI-compatible endpoints of the providers in
`providers.json` (a copy of `data.json` from github.com/mnfst/awesome-free-llm-apis, with
models, context sizes and rate limits). It uses only the Python standard library.

## Usage

```bash
S=skills/free-llm-apis/scripts/llm.py
python3 $S providers                     # which providers are usable (keys found)
python3 $S models groq                   # models and free-tier limits
python3 $S ask kilo "Explain RAFT in 3 lines"          # no key needed
python3 $S ask ovh -m Meta-Llama-3_3-70B-Instruct "…"  # no key needed, 2 RPM
python3 $S ask groq -s "Answer in Italian" "…"
cat file.txt | python3 $S ask openrouter -m google/gemma-4-31b-it:free
```

Options for `ask`: `-m MODEL`, `-s SYSTEM`, `--max-tokens N`, `--timeout S`, `--json`.

## Keys

Keyless: `kilo`, `ovh`, `llm7` (lower limits). The others read a key from an environment
variable: `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `COHERE_API_KEY`,
`NVIDIA_API_KEY`, `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`, `ZAI_API_KEY`,
`AXFORGE_API_KEY`, `GONKA_API_KEY`, `MODELSCOPE_API_KEY`, `SILICONFLOW_API_KEY`,
`AION_API_KEY`, `OVH_AI_ENDPOINTS_ACCESS_TOKEN`, `LLM7_API_KEY`. In a cloud session where
the network proxy injects the key, pass any dummy value.

## Guidance

- Prefer keyless providers first, then Groq (fast) or OpenRouter (many models).
- Respect free-tier rate limits; on HTTP 429 wait or switch provider.
- Free providers may log prompts (OpenRouter, Kilo, NVIDIA): never send secrets or private
  data.
- `CONNECT tunnel failed, response 403` means the sandbox network blocks the host; the
  host must be added to the environment's allowed hosts.
- Model lists change often; if a model id is rejected, try another from `models` or
  query `<base>/models`.
