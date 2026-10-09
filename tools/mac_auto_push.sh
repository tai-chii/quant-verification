#!/bin/zsh
# verification-lab の自動コミット・プッシュ（Mac 用。launchd から10分ごとに実行）
# /lab は Git に触らず、終わったら次の2つのファイルに追記するだけ:
#   .lab_commit_msg   … コミットメッセージ（1件ごとに空行で区切る）
#   .lab_commit_paths … コミットするパス（1行1パス、リポジトリからの相対パス）
# このスクリプトがそれを読んでコミット・プッシュし、2つのファイルを空にする。
# 登録: tools/com.taichi.verification-lab-autopush.plist を参照。ログ: ~/Library/Logs/verification-lab-autopush.log

export PATH="$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="$HOME/ワークスペース/検証/verification-lab"
MSG="$REPO/.lab_commit_msg"
PATHS="$REPO/.lab_commit_paths"

cd "$REPO" || exit 1
echo "== $(date '+%Y-%m-%d %H:%M:%S')"

# 他の PC（Windows の auto_push.ps1 など）の分を先に取り込む
if ! git pull --rebase --autostash -q origin main; then
  git rebase --abort 2>/dev/null
  echo "pull に失敗（衝突の可能性）。手で確認が必要"; exit 1
fi

# /lab の記録があればコミット
if [ -s "$MSG" ] && [ -s "$PATHS" ]; then
  while IFS= read -r p; do
    [ -n "$p" ] && [ -e "$p" ] && git add -A -- "$p"
  done < "$PATHS"
  if ! git diff --cached --quiet; then
    {
      cat "$MSG"
      printf '\nCo-Authored-By: Claude <noreply@anthropic.com>\n'
    } > "$MSG.tmp"
    git commit -q -F "$MSG.tmp" && echo "commit: $(git log -1 --format='%h %s')"
    rm -f "$MSG.tmp"
  fi
  : > "$MSG"; : > "$PATHS"
fi

# 未プッシュのコミットがあれば送る
if [ -n "$(git log origin/main..main --oneline 2>/dev/null)" ]; then
  git push -q origin main && echo "push: ok" || echo "push に失敗"
fi
