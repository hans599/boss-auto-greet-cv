#!/usr/bin/env bash
# git-sync.sh - Windows Git Bash 极简版
# 用法:
#   ./git-sync.sh init <仓库地址>      # 新电脑首次克隆   https://github.com/hans599/boss-auto-greet-cv.git
#   ./git-sync.sh pull                 # 拉取远程更新
#   ./git-sync.sh push [message]       # add + commit + push
#   ./git-sync.sh remote <仓库地址>    # 关联 origin 并首次推送

set -e

case "$1" in
  init)
    if [ -z "$2" ]; then
      echo "用法: $0 init <仓库地址>"
      exit 1
    fi
    dir=$(basename "$2" .git)
    git clone "$2" "$dir"
    echo "已克隆到 ./$dir"
    echo "请手动执行: cd $dir"
    ;;

  pull)
    git pull
    ;;

  push)
    msg="$2"
    if [ -z "$msg" ]; then
      read -p "请输入 commit message: " msg
    fi
    if [ -z "$msg" ]; then
      echo "commit message 不能为空"
      exit 1
    fi
    git add -A
    git commit -m "$msg" || true
    # 首次推送自动加 -u，之后正常 push
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
      git push
    else
      branch=$(git symbolic-ref --short HEAD)
      git push -u origin "$branch"
    fi
    ;;

  remote)
    if [ -z "$2" ]; then
      echo "用法: $0 remote <仓库地址>"
      exit 1
    fi
    # 已存在 origin 就先删掉，避免报错
    if git remote get-url origin >/dev/null 2>&1; then
      git remote remove origin
    fi
    git remote add origin "$2"
    echo "已关联 origin -> $2"
    # 本地无提交时先提交
    if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
      git add -A
      read -p "本地还没有提交，请输入初始 commit message: " msg
      [ -n "$msg" ] || msg="initial commit"
      git commit -m "$msg"
    fi
    branch=$(git symbolic-ref --short HEAD)
    git push -u origin "$branch"
    echo "✅ 首次推送完成，分支 $branch 已绑定 origin/$branch"
    ;;

  *)
    echo "用法:"
    echo "  $0 init <仓库地址>      # 首次克隆"
    echo "  $0 pull                 # 拉取更新"
    echo "  $0 push [message]       # 提交并推送"
    echo "  $0 remote <仓库地址>    # 关联 origin 并首次推送"
    exit 1
    ;;
esac