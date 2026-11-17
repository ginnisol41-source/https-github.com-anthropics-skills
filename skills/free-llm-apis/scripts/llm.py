#!/usr/bin/env python3
"""Call free-tier LLM APIs (from mnfst/awesome-free-llm-apis) through their
OpenAI-compatible chat endpoints. Standard library only.

  python3 llm.py providers                 # list providers, key status
  python3 llm.py models <provider>         # models listed for a provider
  python3 llm.py ask <provider> [-m MODEL] [-s SYSTEM] [--max-tokens N] "prompt"
  echo "prompt" | python3 llm.py ask kilo

<provider> is a slug (see `providers`). Keys are read from environment variables.
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DATA = pathlib.Path(__file__).resolve().parent.parent / "providers.json"

# slug -> (name in providers.json, API key env var or None if keyless,
#          OpenAI-compatible base URL override or None, default model)
PROVIDERS = {
    "kilo":       ("Kilo Code", None, None, "kilo-auto/free"),
    "ovh":        ("OVHcloud AI Endpoints", "OVH_AI_ENDPOINTS_ACCESS_TOKEN", None, "gpt-oss-120b"),
    "groq":       ("Groq", "GROQ_API_KEY", None, "openai/gpt-oss-120b"),
    "openrouter": ("OpenRouter", "OPENROUTER_API_KEY", None, "google/gemma-4-31b-it:free"),
    "gemini":     ("Google Gemini", "GEMINI_API_KEY",
                   "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "cohere":     ("Cohere", "COHERE_API_KEY",
                   "https://api.cohere.ai/compatibility/v1", "command-a-03-2025"),
    "nvidia":     ("NVIDIA NIM", "NVIDIA_API_KEY", None, "openai/gpt-oss-20b"),
    "cloudflare": ("Cloudflare Workers AI", "CLOUDFLARE_API_TOKEN",
                   "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
                   "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
    "zai":        ("Z AI (Zhipu AI)", "ZAI_API_KEY", None, "glm-4.7-flash"),
    "axforge":    ("AxForge", "AXFORGE_API_KEY", None, None),
    "gonka":      ("Gonka Broker", "GONKA_API_KEY", None, None),
    "llm7":       ("LLM7.io", "LLM7_API_KEY", None, "gpt-oss:20b"),
    "modelscope": ("ModelScope", "MODELSCOPE_API_KEY", None, None),
    "siliconflow": ("SiliconFlow", "SILICONFLOW_API_KEY", None, None),
    "aion":       ("Aion Labs", "AION_API_KEY", None, "aion-labs/aion-3.0-mini"),
}
# Providers that work without a key (key used if present).
KEY_OPTIONAL = {"kilo", "ovh", "llm7"}


def load():
    data = json.loads(DATA.read_text())
    return {p["name"]: p for p in data["providers"]}


def resolve(slug):
    if slug not in PROVIDERS:
        sys.exit(f"Unknown provider '{slug}'. Choose from: {', '.join(PROVIDERS)}")
    name, env, base, default = PROVIDERS[slug]
    info = load().get(name, {})
    base = base or info.get("baseUrl")
    if "{account_id}" in base:
        acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        if not acct:
            sys.exit("Set CLOUDFLARE_ACCOUNT_ID for Cloudflare Workers AI.")
        base = base.replace("{account_id}", acct)
    key = os.environ.get(env) if env else None
    if env and not key and slug not in KEY_OPTIONAL:
        sys.exit(f"{name} needs an API key in ${env} (get one at {info.get('url')}).")
    if not default and info.get("models"):
        default = info["models"][0]["id"]
    return name, base.rstrip("/"), key, default, info


def cmd_providers(_):
    for slug, (name, env, _b, _d) in PROVIDERS.items():
        if slug in KEY_OPTIONAL and not (env and os.environ.get(env)):
            status = "no key needed"
        elif env and os.environ.get(env):
            status = f"key set (${env})"
        else:
            status = f"missing ${env}"
        print(f"{slug:12} {name:24} {status}")


def cmd_models(a):
    name, base, _k, default, info = resolve_no_key(a.provider)
    print(f"{name}  base={base}  default={default}")
    for m in info.get("models", []):
        print(f"  {m['id']:50} ctx={m.get('context')} out={m.get('maxOutput')} limit={m.get('rateLimit')}")


def resolve_no_key(slug):
    name, env, base, default = PROVIDERS[slug] if slug in PROVIDERS else sys.exit(f"Unknown provider '{slug}'")
    info = load().get(name, {})
    return name, base or info.get("baseUrl"), None, default or (info.get("models") or [{}])[0].get("id"), info


def cmd_ask(a):
    prompt = a.prompt or sys.stdin.read()
    if not prompt.strip():
        sys.exit("Empty prompt.")
    name, base, key, default, _ = resolve(a.provider)
    msgs = ([{"role": "system", "content": a.system}] if a.system else []) + [{"role": "user", "content": prompt}]
    body = {"model": a.model or default, "messages": msgs, "max_tokens": a.max_tokens}
    headers = {"Content-Type": "application/json", "User-Agent": "free-llm-apis-skill/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/chat/completions", json.dumps(body).encode(), headers)
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{name} HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"{name} unreachable: {e.reason}")
    if a.json:
        print(json.dumps(out, indent=2))
        return
    msg = out["choices"][0]["message"]
    print(msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or "")
    u = out.get("usage")
    if u:
        print(f"\n[{name} · {out.get('model', body['model'])} · {u.get('total_tokens')} tokens]", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("providers").set_defaults(f=cmd_providers)
    m = sub.add_parser("models"); m.add_argument("provider"); m.set_defaults(f=cmd_models)
    q = sub.add_parser("ask")
    q.add_argument("provider"); q.add_argument("prompt", nargs="?")
    q.add_argument("-m", "--model"); q.add_argument("-s", "--system")
    q.add_argument("--max-tokens", type=int, default=1024)
    q.add_argument("--timeout", type=int, default=120)
    q.add_argument("--json", action="store_true", help="print the raw response")
    q.set_defaults(f=cmd_ask)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
