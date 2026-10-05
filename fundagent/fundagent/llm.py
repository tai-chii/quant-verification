"""LLMクライアント（Anthropic）。JSONを返させることに特化。

- dry_run=True なら API を叩かずスタブ応答を返す（キー無しで配線確認できる）
- トークン使用量を積算し、概算コストを出す
"""
from __future__ import annotations
import json, os, re, sys, time

# 概算単価（USD / 1Mトークン）。変わるので `run.py models` と公式価格表で随時更新する。
PRICE_USD_PER_MTOK = {
    "haiku":  {"in": 1.00, "out": 5.00},
    "sonnet": {"in": 3.00, "out": 15.00},
    "opus":   {"in": 15.00, "out": 75.00},
}


def _price_key(model: str) -> str:
    m = model.lower()
    for k in ("haiku", "sonnet", "opus"):
        if k in m:
            return k
    return "sonnet"


class LLM:
    def __init__(self, cfg: dict, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.usage = []  # [{model,in,out}]
        self.client = None
        if not dry_run:
            try:
                import anthropic
            except ImportError:
                sys.exit("anthropic SDK が未導入です: pip install anthropic")
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                sys.exit("環境変数 ANTHROPIC_API_KEY が未設定です（--dry-run なら不要）")
            self.client = anthropic.Anthropic(api_key=key)

    # ---- 低レベル ----
    def call_json(self, model: str, system: str, user: str, stub: dict) -> dict:
        if self.dry_run:
            self.usage.append({"model": model, "in": len(system + user) // 3, "out": 200})
            return stub
        last = None
        for attempt in range(3):
            try:
                msg = self.client.messages.create(
                    model=model,
                    max_tokens=self.cfg["llm"]["max_output_tokens"],
                    temperature=self.cfg["llm"]["temperature"],
                    system=system,
                    messages=[{"role": "user", "content": user},
                              {"role": "assistant", "content": "{"}],
                )
                self.usage.append({"model": model,
                                   "in": msg.usage.input_tokens,
                                   "out": msg.usage.output_tokens})
                text = "{" + "".join(b.text for b in msg.content if b.type == "text")
                return self._parse(text)
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM呼び出しに3回失敗: {last}")

    @staticmethod
    def _parse(text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.S)
            if not m:
                raise
            return json.loads(m.group(0))

    # ---- コスト ----
    def cost_usd(self) -> float:
        total = 0.0
        for u in self.usage:
            p = PRICE_USD_PER_MTOK[_price_key(u["model"])]
            total += u["in"] / 1e6 * p["in"] + u["out"] / 1e6 * p["out"]
        return total

    def usage_note(self) -> str:
        tin = sum(u["in"] for u in self.usage)
        tout = sum(u["out"] for u in self.usage)
        usd = self.cost_usd()
        return f"calls={len(self.usage)} in={tin} out={tout} 概算${usd:.4f} (≈{usd*155:.1f}円)"
