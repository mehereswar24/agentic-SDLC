"""Live WS smoke test — connects, POSTs a run, prints every WS message in order.

Run with:  uv run python scripts/ws_smoketest.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import suppress

import httpx
from httpx_ws import WebSocketDisconnect, aconnect_ws

BASE = "http://127.0.0.1:8765"
WS_BASE = "ws://127.0.0.1:8765"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        post = await client.post(
            "/api/runs", json={"prompt": "build a simple expense tracker app"}
        )
        if post.status_code != 201:
            print(f"POST failed: {post.status_code} {post.text}")
            return 1
        run_id = post.json()["id"]
        print(f"[ws-smoke] run_id={run_id}")

        async with aconnect_ws(f"{WS_BASE}/ws/runs/{run_id}", client) as ws:
            try:
                idx = 0
                while True:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=120)
                    idx += 1
                    kind = msg.get("type")
                    if kind == "snapshot":
                        run = msg["run"]
                        print(
                            f"  {idx:2}. SNAPSHOT status={run['status']} "
                            f"steps={len(run['steps'])} artifacts={len(run['artifacts'])}"
                        )
                    elif kind == "event":
                        data = msg["data"]
                        et = data["type"]
                        payload = data.get("payload", {})
                        # Summarize payload — full thing is noisy
                        keys = sorted(payload.keys())
                        short = {k: payload[k] for k in keys if k in {
                            "node", "iteration", "score", "should_revise",
                            "kind", "version", "latency_ms", "tokens_in",
                            "tokens_out", "error", "prd_title",
                        }}
                        print(f"  {idx:2}. EVENT {et:22} {json.dumps(short, default=str)}")
                    else:
                        print(f"  {idx:2}. OTHER {msg}")
            except WebSocketDisconnect as exc:
                print(f"[ws-smoke] server closed ws cleanly: code={exc.code} reason={exc.reason!r}")
            except TimeoutError:
                print("[ws-smoke] TIMEOUT waiting for next ws message")
                return 2

        # Verify final state via REST too.
        final = (await client.get(f"/api/runs/{run_id}")).json()
        print(f"[ws-smoke] final status={final['status']} steps={len(final['steps'])} "
              f"artifacts={len(final['artifacts'])}")
        return 0 if final["status"] == "completed" else 3


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        sys.exit(asyncio.run(main()))
