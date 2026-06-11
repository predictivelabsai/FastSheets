"""FastSheets AI — grounded chat over computed sheet values + slash-commands."""
from __future__ import annotations

import json
import os

import db
import engine

PROVIDER = os.getenv("MODEL_PROVIDER", "xai")
MODEL = os.getenv("MODEL_NAME", "grok-4-1-fast-reasoning")


def _sheet_text(sid, max_rows=14, max_cols=8) -> str:
    s = db.sheet(sid)
    raw = db.cells(sid)
    sheet = engine.Sheet(raw)
    used_r = max([r for (r, c) in raw] + [0]) + 1
    used_c = max([c for (r, c) in raw] + [0]) + 1
    used_r, used_c = min(used_r, max_rows), min(used_c, max_cols)
    lines = [f"Sheet '{s['title']}':"]
    for r in range(used_r):
        cells = []
        for c in range(used_c):
            ref = engine.num_to_col(c) + str(r + 1)
            disp = sheet.display(r, c)
            if disp != "":
                rawv = raw.get((r, c), "")
                cells.append(f"{ref}={disp}" + (f" [{rawv}]" if rawv.startswith("=") else ""))
        if cells:
            lines.append("  " + " | ".join(cells))
    return "\n".join(lines)


def snapshot() -> str:
    parts = ["SHEETS SNAPSHOT (synthetic; cell=value, [formula] shown where present):"]
    for s in db.sheets():
        parts.append(_sheet_text(s["id"]))
    return "\n\n".join(parts)


SYSTEM_PROMPT = """You are the FastSheets assistant, embedded in a spreadsheet app.
Help the user understand their data, totals and formulas, and suggest formulas. Be concise;
use Markdown. The SHEETS SNAPSHOT below gives each cell's computed value and, for formula
cells, the formula in [brackets]. Base answers on it; if a value isn't shown, say so."""


def handle_command(text):
    if not text.startswith("/"):
        return None
    cmd = text[1:].split()[0].lower() if len(text) > 1 else ""
    if cmd in ("help", "?"):
        return ("**FastSheets shortcuts**\n\n- `/sheets` — list your sheets\n\n"
                "Ask about totals, or 'explain the formula in E7', or 'what formula sums B2:B6?'")
    if cmd == "sheets":
        out = ["**Your sheets**\n", "| Sheet | Size | Cells |", "| --- | --- | --- |"]
        for s in db.sheets():
            out.append(f"| {s['title']} | {s['n_rows']}×{s['n_cols']} | {s['n']} |")
        return "\n".join(out)
    return f"Unknown command `/{cmd}`. Try `/help`."


async def stream_chat(message):
    cmd = handle_command(message)
    if cmd is not None:
        yield f"data: {json.dumps({'token': cmd})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return
    system = SYSTEM_PROMPT + "\n\n" + snapshot()
    try:
        async for tok in _provider_stream(system, message):
            yield f"data: {json.dumps({'token': tok})}\n\n"
    except Exception as e:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield f"data: {json.dumps({'done': True})}\n\n"


async def _provider_stream(system, message):
    import httpx
    provider, model = PROVIDER, MODEL
    if provider in ("xai", "openai"):
        url = "https://api.x.ai/v1/chat/completions" if provider == "xai" else "https://api.openai.com/v1/chat/completions"
        key = os.getenv("XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, headers={"Authorization": f"Bearer {key}"},
                                     json={"model": model, "stream": True,
                                           "messages": [{"role": "system", "content": system},
                                                        {"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            tok = json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    elif provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                                     json={"model": model, "max_tokens": 1500, "stream": True, "system": system,
                                           "messages": [{"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if ev.get("type") == "content_block_delta":
                                tok = ev.get("delta", {}).get("text", "")
                                if tok: yield tok
                        except json.JSONDecodeError:
                            pass
    elif provider == "google":
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, json={"system_instruction": {"parts": [{"text": system}]},
                                                        "contents": [{"role": "user", "parts": [{"text": message}]}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            tok = json.loads(line[6:])["candidates"][0]["content"]["parts"][0].get("text", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    else:
        yield "No LLM provider configured. Slash-commands like /sheets work without a key."


def _no_key(provider):
    env = {"xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY"}[provider]
    return (f"⚠ No **{env}** set, so free-form chat is disabled. Add it to `.env` and restart. "
            "The `/sheets` command works without any key.")
