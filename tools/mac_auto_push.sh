#!/bin/zsh
# verification-lab の自動コミット・プッシュ（Mac 用。launchd から10分ごとに実行）
#
# 1回の /lab ＝ 1コミット＝1プッシュ（GitHub の push 数・コミット数が行動回数になるように）。
# /lab は Git に触らず、終わったら .lab_pending/ に新しいファイルを1つ作るだけ:
#   .lab_pending/<YYYYmmdd-HHMMSS>_<Qxxx>.txt
#     1行目        コミットメッセージの件名（例: lab: Q141 … — 棄却）
#     2行目        空行
#     3行目以降    コミットするパス（1行1パス、リポジトリからの相対パス）
# このスクリプトがファイル名順に1件ずつ「コミット→プッシュ」し、済んだファイルを消す。
# 登録: tools/com.taichi.verification-lab-autopush.plist。ログ: ~/Library/Logs/verification-lab-autopush.log

export PATH="$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="$HOME/ワークスペース/検証/verification-lab"
PENDING="$REPO/.lab_pending"

cd "$REPO" || exit 1
# 大きめのプッシュで HTTP 400（RPC failed）になるのを防ぐ
[ "$(git config --get http.postBuffer)" = "524288000" ] || git config http.postBuffer 524288000
[ -d "$PENDING" ] || exit 0
setopt null_glob
files=("$PENDING"/*.txt)
(( ${#files} )) || exit 0
echo "== $(date '+%Y-%m-%d %H:%M:%S') 未処理 ${#files} 件"

for f in "${files[@]}"; do
  # 他の PC（Windows の auto_push.ps1 など）の分を先に取り込む
  if ! git pull --rebase --autostash -q origin main; then
    git rebase --abort 2>/dev/null
    echo "pull に失敗（衝突の可能性）。$f 以降は次回に回す"; exit 1
  fi

  subject=$(head -n 1 "$f")
  tail -n +3 "$f" | while IFS= read -r p; do
    [ -n "$p" ] && [ -e "$p" ] && git add -A -- "$p"
  done

  if git diff --cached --quiet; then
    echo "変更なし: $(basename $f)（$subject）"
  else
    printf '%s\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n' "$subject" > "$f.msg"
    git commit -q -F "$f.msg" && echo "commit: $(git log -1 --format='%h %s')"
    rm -f "$f.msg"
    if git push -q origin main; then
      echo "push: ok"
    else
      echo "push に失敗。コミットは残し、$f 以降は次回に回す"; exit 1
    fi
  fi
  rm -f "$f"
done

# 前回プッシュに失敗して残ったコミットがあれば送る
if [ -n "$(git log origin/main..main --oneline 2>/dev/null)" ]; then
  git push -q origin main && echo "push（残り）: ok"
fi
exit 0
