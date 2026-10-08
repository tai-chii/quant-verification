"""麻雀バックテスト用ボット定義

- BaselineBot : mjai同梱のRulebaseBot(受け入れ枚数最大化)を安全化したもの
- TaichiBot   : taichiのマイルールをBaselineに上書き実装したもの
"""
import json
from mjai import Bot
from mjai.bot.rulebase import RulebaseBot

DRAGONS = ["P", "F", "C"]          # 白 発 中
WINDS = ["E", "S", "W", "N"]
HONORS = WINDS + DRAGONS


class SafeBot(Bot):
    """不正打牌でMatchが落ちるのを防ぐ安全層。"""

    def think(self) -> str:
        try:
            resp = self.think_impl()
        except Exception:
            resp = None
        if resp is None or not self._valid(resp):
            resp = self._fallback()
        return resp

    def _valid(self, resp: str) -> bool:
        try:
            return bool(self.validate_reaction(resp))
        except Exception:
            return False

    def _fallback(self) -> str:
        if self.can_discard:
            d = self._discardable
            t = self.last_self_tsumo
            if t and t in d:
                return self.action_discard(t)
            if d:
                return self.action_discard(d[0])
        return self.action_nothing()

    def think_impl(self) -> str:
        raise NotImplementedError


class BaselineBot(RulebaseBot):
    """受け入れ枚数最大化 + 役牌ポン + 常時即リーチ。現代定石寄りの基準線。"""
    pass


class TaichiBot(RulebaseBot):
    """taichiのマイルールを実装。

    R1 序盤は字牌優先。切り順 客風→白→発→中→場風→自風
    R2 役がつく字牌の対子のみ保持(客風の対子は切る)
    R3 鳴かない。終盤の形式聴牌のみ例外
    R4 残り2枚が河に出た字牌対子は雀頭/安牌として保持
    R5 孤立牌は端から、繋がりにくい牌から
    R6 愚形聴牌は3巡黙聴で様子見。他家リーチなら追っかけ
    R7 先制リーチには聴牌していなければベタオリ
    """

    OPENING_TURNS = 6      # R1を適用する巡目
    DAMATEN_LIMIT = 3      # R6の様子見巡数
    LATE_TURN = 13         # R3の終盤判定

    def __init__(self, player_id: int = 0):
        super().__init__(player_id)
        self.opp_riichi = set()
        self.damaten_turns = 0

    # ---- イベント追跡(他家リーチの検出) ----
    def react(self, input_str: str) -> str:
        try:
            for ev in json.loads(input_str):
                t = ev.get("type")
                if t in ("start_kyoku", "start_game"):
                    self.opp_riichi = set()
                    self.damaten_turns = 0
                elif t == "reach" and ev.get("actor") != self.player_id:
                    self.opp_riichi.add(ev["actor"])
        except Exception:
            pass
        return super().react(input_str)

    # ---- 補助 ----
    @property
    def turn(self) -> int:
        try:
            return int(self.player_state.at_turn)
        except Exception:
            return 0

    def _counts(self):
        c = {}
        for t in self.tehai_mjai:
            k = t[:2] if len(t) > 2 else t
            k = k.replace("r", "") if k.endswith("r") else k
            c[k] = c.get(k, 0) + 1
        return c

    def _honor_rank(self, tile: str) -> int:
        """小さいほど先に切る。R1の切り順。"""
        if tile in WINDS and tile != self.jikaze and tile != self.bakaze:
            return 0                      # 客風
        if tile == "P":
            return 1                      # 白
        if tile == "F":
            return 2                      # 発
        if tile == "C":
            return 3                      # 中
        if tile == self.bakaze:
            return 4                      # 場風
        if tile == self.jikaze:
            return 5                      # 自風
        return 9

    def _honor_to_dump(self):
        """R1/R2/R4: 切ってよい字牌を切り順に並べる。"""
        cnt = self._counts()
        seen = self.tiles_seen
        out = []
        for t in self._discardable:
            base = t[:2] if len(t) > 2 else t
            if base not in HONORS:
                continue
            n = cnt.get(base, 0)
            if n >= 2:
                # R2: 役がつく字牌の対子は保持
                if self.is_yakuhai(base):
                    continue
                # R4: 残り2枚が河に出ていれば雀頭/安牌として保持
                if seen.get(base, 0) >= 4:
                    continue
            out.append(t)
        out.sort(key=lambda x: self._honor_rank(x[:2] if len(x) > 2 else x))
        return out

    def _isolation(self, tile: str) -> int:
        """R5: 周辺2つ以内の手牌枚数。小さいほど孤立=先に切る。"""
        base = tile[:2] if len(tile) > 2 else tile
        if base in HONORS:
            return -1
        cnt = self._counts()
        num, suit = int(base[0]), base[1]
        score = 0
        for d in (-2, -1, 1, 2):
            n = num + d
            if 1 <= n <= 9:
                w = 2 if abs(d) == 1 else 1
                score += w * cnt.get(f"{n}{suit}", 0)
        score += 3 * (cnt.get(base, 0) - 1)
        return score

    def _terminal_rank(self, tile: str) -> int:
        """R5: 端ほど先に切る。"""
        base = tile[:2] if len(tile) > 2 else tile
        if base in HONORS:
            return -1
        n = int(base[0])
        return min(n - 1, 9 - n)          # 1,9->0  2,8->1 ... 5->4

    def _safest(self) -> str:
        """R7: ベタオリ時の打牌選択。現物 > 見えている枚数の多い牌。"""
        genbutsu = set()
        for a in self.opp_riichi:
            genbutsu |= set(self.discarded_tiles(a))
        seen = self.tiles_seen
        best, key = None, None
        for t in self._discardable:
            base = t[:2] if len(t) > 2 else t
            k = (1 if base in genbutsu else 0,
                 1 if base in HONORS else 0,
                 seen.get(base, 0))
            if key is None or k > key:
                best, key = t, k
        return best

    @property
    def _discardable(self):
        """mjaiのdiscardable_tilesは赤ドラでKeyErrorを起こすため自前実装。"""
        out = []
        for t in self.tehai_mjai:
            base = t[:2] if len(t) > 2 else t
            if not self.forbidden_tiles.get(base, False):
                out.append(t)
        return out

    def _emit(self, tile):
        """打牌が合法かを最終確認してから返す。"""
        d = self._discardable
        if tile and tile in d:
            return self.action_discard(tile)
        t = self.last_self_tsumo
        if t and t in d:
            return self.action_discard(t)
        return self.action_discard(d[0]) if d else self.action_nothing()

    # ---- 本体 ----
    def think(self) -> str:
        if self.can_tsumo_agari:
            return self.action_tsumo_agari()
        if self.can_ron_agari:
            return self.action_ron_agari()

        # R6: リーチ判断
        if self.can_riichi and not self.self_riichi_declared:
            waits = 0
            try:
                waits = sum(1 for w in self.player_state.waits if w)
            except Exception:
                waits = 2
            gukei = waits <= 1
            if (gukei and not self.opp_riichi
                    and self.damaten_turns < self.DAMATEN_LIMIT
                    and self.turn < 15):
                self.damaten_turns += 1     # 黙聴で様子見
            else:
                return self.action_riichi()

        # R3: 鳴かない。終盤の形式聴牌のみ例外
        if (self.can_pon or self.can_chi) and self.turn >= self.LATE_TURN:
            if self.can_pon:
                for pon in self.find_pon_candidates():
                    if pon["next_shanten"] == 0:
                        return self.action_pon(consumed=pon["consumed"])
            if self.can_chi:
                for c in self.find_chi_candidates():
                    if c["next_shanten"] == 0:
                        return self.action_chi(consumed=c["consumed"])

        if not self.can_discard:
            return self.action_nothing()

        if self.self_riichi_accepted:
            return self.action_discard(self.last_self_tsumo)

        # リーチ宣言直後は打牌が制限される。独自ロジックを通さない。
        if self.self_riichi_declared:
            legal = self.discardable_tiles_riichi_declaration
            t = self.last_self_tsumo
            return self.action_discard(
                t if t in legal else (legal[0] if legal else t))

        # R7: 先制リーチに聴牌していなければベタオリ
        if self.opp_riichi and self.shanten > 0:
            t = self._safest()
            if t:
                return self._emit(t)

        # 副露している場合は専用ロジック(mjaiの受け入れ計算が使えない)
        if getattr(self, "is_open", False):
            t = self._meld_discard()
            if t:
                return self._emit(t)

        # R1: 序盤は字牌から
        if self.turn <= self.OPENING_TURNS:
            h = self._honor_to_dump()
            if h:
                return self._emit(h[0])

        # 受け入れ最大化 + R5でタイブレーク
        cands = [c for c in self.find_improving_tiles()
                 if c["discard_tile"]
                 and not self.forbidden_tiles.get(c["discard_tile"][:2], True)]
        if cands:
            best = max(c["ukeire"] for c in cands)
            tied = [c for c in cands if c["ukeire"] == best]
            tied.sort(key=lambda c: (self._isolation(c["discard_tile"]),
                                     self._terminal_rank(c["discard_tile"])))
            return self._emit(tied[0]["discard_tile"])

        # 字牌が残っていれば切り順に従う
        h = self._honor_to_dump()
        if h:
            return self._emit(h[0])
        return super().think()


class TaichiNoFold(TaichiBot):
    """R7(先制リーチへのベタオリ)だけを外した版。守備ルールの寄与を測る。"""
    def think(self) -> str:
        self.opp_riichi = set()
        return super().think()


class TaichiCallOK(TaichiBot):
    """R3(鳴かない)だけを外した版。役牌ポンを解禁する。"""
    LATE_TURN = 0


class CautiousBot(RulebaseBot):
    """対照用の「慎重な場」。受け入れ最大化+役牌ポン+即リーだが、
    他家リーチには聴牌していなければベタオリする。天鳳上位帯の模擬。"""

    def __init__(self, player_id: int = 0):
        super().__init__(player_id)
        self.opp_riichi = set()

    def react(self, input_str: str) -> str:
        try:
            for ev in json.loads(input_str):
                t = ev.get("type")
                if t in ("start_kyoku", "start_game"):
                    self.opp_riichi = set()
                elif t == "reach" and ev.get("actor") != self.player_id:
                    self.opp_riichi.add(ev["actor"])
        except Exception:
            pass
        return super().react(input_str)

    @property
    def _discardable(self):
        out = []
        for t in self.tehai_mjai:
            base = t[:2] if len(t) > 2 else t
            if not self.forbidden_tiles.get(base, False):
                out.append(t)
        return out

    def think(self) -> str:
        if (self.opp_riichi and self.can_discard
                and not self.self_riichi_declared
                and not self.self_riichi_accepted
                and self.shanten > 0):
            genbutsu = set()
            for a in self.opp_riichi:
                genbutsu |= set(self.discarded_tiles(a))
            seen = self.tiles_seen
            best, key = None, None
            for t in self._discardable:
                base = t[:2] if len(t) > 2 else t
                k = (1 if base in genbutsu else 0,
                     1 if base in HONORS else 0, seen.get(base, 0))
                if key is None or k > key:
                    best, key = t, k
            if best:
                return self.action_discard(best)
        return super().think()


class TaichiInstantRiichi(TaichiBot):
    """R6を反転。愚形でも即リーチする版。"""
    DAMATEN_LIMIT = 0


class TaichiYakuhaiPon(TaichiBot):
    """R3を現実的な形に緩和。役牌(自風/場風/三元牌)のポンだけを解禁する。
    向聴が進む場合のみ受ける。チーと非役牌ポンは従来通り拒否。"""

    def think(self) -> str:
        if (self.can_pon and not self.self_riichi_declared
                and self.last_kawa_tile
                and self.is_yakuhai(self.last_kawa_tile)):
            try:
                for pon in self.find_pon_candidates():
                    if pon["current_shanten"] > pon["next_shanten"]:
                        return self.action_pon(consumed=pon["consumed"])
            except Exception:
                pass
        return super().think()


class TaichiPonInstant(TaichiYakuhaiPon):
    """役牌ポン解禁 + 愚形即リーチ(前回の検証で優位と出た改良を併用)。"""
    DAMATEN_LIMIT = 0


# ============================================================
# 副露手の打牌ロジック（mjaiのfind_improving_tilesは副露手で
# 候補を返さないため、独自に向聴数最小化で打牌を選ぶ）
# ============================================================
from mahjong.shanten import Shanten as _Shanten   # noqa: E402

_ST = _Shanten()
_TILES34 = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + \
           ["E", "S", "W", "N", "P", "F", "C"]
_IDX = {t: i for i, t in enumerate(_TILES34)}


def _base(t):
    return t[:2] if len(t) > 2 else t


class MeldAwareMixin:
    """副露している間の打牌を向聴数最小化で決める。"""

    def _full_vec34(self):
        """手牌 + 副露を13(14)枚相当の34配列に展開する。"""
        v = list(self.tehai_vec34)
        for ev in self.get_call_events(self.player_id):
            t = ev.get("type")
            tiles = []
            if t in ("pon", "chi", "daiminkan", "kakan"):
                tiles = [ev.get("pai")] + list(ev.get("consumed") or [])
            elif t == "ankan":
                tiles = list(ev.get("consumed") or [])
            for x in tiles[:3]:
                if x:
                    i = _IDX.get(_base(x))
                    if i is not None:
                        v[i] += 1
        return v

    @property
    def is_open(self):
        return len(self.get_call_events(self.player_id)) > 0

    def _meld_discard(self):
        """副露手の打牌。向聴数最小 → 孤立度 → 端 の順で選ぶ。"""
        v = self._full_vec34()
        best, key = None, None
        for t in self._discardable:
            i = _IDX.get(_base(t))
            if i is None or v[i] == 0:
                continue
            v[i] -= 1
            try:
                sh = _ST.calculate_shanten(v, use_chiitoitsu=False,
                                           use_kokushi=False)
            except Exception:
                sh = 99
            v[i] += 1
            k = (-sh, -self._isolation(t), -self._terminal_rank(t))
            if key is None or k > key:
                best, key = t, k
        return best


# 既存クラスに副露対応を後付けする
for _n in ("_full_vec34", "is_open", "_meld_discard"):
    setattr(TaichiBot, _n, getattr(MeldAwareMixin, _n))


class BaselineFixed(RulebaseBot):
    """ベースラインの副露バグを修正した版。対戦相手(場)として使う。"""

    @property
    def _discardable(self):
        out = []
        for t in self.tehai_mjai:
            if not self.forbidden_tiles.get(_base(t), False):
                out.append(t)
        return out

    def _isolation(self, tile):
        b = _base(tile)
        if b in HONORS:
            return -1
        cnt = {}
        for t in self.tehai_mjai:
            cnt[_base(t)] = cnt.get(_base(t), 0) + 1
        num, suit = int(b[0]), b[1]
        sc = 0
        for d in (-2, -1, 1, 2):
            n = num + d
            if 1 <= n <= 9:
                sc += (2 if abs(d) == 1 else 1) * cnt.get(f"{n}{suit}", 0)
        return sc + 3 * (cnt.get(b, 0) - 1)

    def _terminal_rank(self, tile):
        b = _base(tile)
        if b in HONORS:
            return -1
        n = int(b[0])
        return min(n - 1, 9 - n)

    def think(self):
        if (self.is_open and self.can_discard
                and not self.can_tsumo_agari and not self.can_ron_agari
                and not self.can_pon and not self.can_chi):
            t = self._meld_discard()
            if t and t in self._discardable:
                return self.action_discard(t)
        return super().think()


for _n in ("_full_vec34", "is_open", "_meld_discard"):
    setattr(BaselineFixed, _n, getattr(MeldAwareMixin, _n))
