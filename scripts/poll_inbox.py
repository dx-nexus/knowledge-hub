#!/usr/bin/env python3
"""
poll_inbox.py
=============
リモートの inbox/next_request.json を GitHub API で監視し、
変更を検知したら git pull → claude コマンドを起動する自動化スクリプト。

【起動方法】
  python scripts/poll_inbox.py

【必要な環境変数】
  GITHUB_TOKEN  : GitHub Personal Access Token（repo スコープ）
  GITHUB_REPO   : "owner/repo" 形式（例: dx-nexus/knowledge-hub）

【オプション環境変数】
  POLL_INTERVAL : チェック間隔（秒）。デフォルト 60
  INBOX_PATH    : 監視ファイルのパス。デフォルト inbox/next_request.json
  BRANCH        : 監視ブランチ。デフォルト main
  CLAUDE_CMD    : claude 呼び出しコマンド。デフォルト "claude"

【inbox/next_request.json のフォーマット】
  {
    "task": "タスクの指示テキスト",
    "timestamp": "2026-05-18T10:00:00",
    "requested_by": "human"
  }
  ※ 空の {} はペンディングなしとして無視される
"""

import os
import sys
import json
import time
import hashlib
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "dx-nexus/knowledge-hub")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))
INBOX_PATH    = os.environ.get("INBOX_PATH", "inbox/next_request.json")
BRANCH        = os.environ.get("BRANCH", "main")
CLAUDE_CMD    = os.environ.get("CLAUDE_CMD", "claude")

API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{INBOX_PATH}?ref={BRANCH}"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_remote_file() -> dict | None:
    """GitHub API でファイルのメタ情報＋コンテンツを取得する。"""
    req = urllib.request.Request(API_URL)
    req.add_header("Accept", "application/vnd.github.v3+json")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log(f"API エラー {e.code}: {e.reason}")
        return None
    except Exception as e:
        log(f"ネットワークエラー: {e}")
        return None


def decode_content(data: dict) -> dict:
    """Base64 エンコードされた JSON を Python dict に変換する。"""
    import base64
    raw = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(raw)


def git_pull() -> bool:
    """git pull origin main を実行して成功可否を返す。"""
    result = subprocess.run(
        ["git", "pull", "origin", BRANCH],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log(f"git pull 成功: {result.stdout.strip()}")
        return True
    log(f"git pull 失敗: {result.stderr.strip()}")
    return False


def run_claude(task: str) -> None:
    """claude コマンドをバックグラウンドで起動する。"""
    log(f"Claude 起動: {task[:80]}...")
    subprocess.Popen(
        [CLAUDE_CMD, "--dangerously-skip-permissions", "-p", task],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def clear_inbox() -> None:
    """ローカルの inbox/next_request.json をリセット（処理済みマーク）する。"""
    inbox_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        INBOX_PATH
    )
    with open(inbox_file, "w", encoding="utf-8") as f:
        json.dump({}, f)
    log("inbox をリセットしました（ローカル）")


def main() -> None:
    if not GITHUB_TOKEN:
        log("警告: GITHUB_TOKEN が未設定です。プライベートリポジトリでは動作しません。")

    log(f"監視開始: {GITHUB_REPO}/{INBOX_PATH} (間隔: {POLL_INTERVAL}秒)")

    last_sha: str = ""

    while True:
        try:
            data = get_remote_file()
            if data is None:
                time.sleep(POLL_INTERVAL)
                continue

            current_sha: str = data.get("sha", "")

            if current_sha == last_sha:
                # 変化なし
                time.sleep(POLL_INTERVAL)
                continue

            log(f"変更検知 SHA: {last_sha[:7] or 'initial'} → {current_sha[:7]}")
            last_sha = current_sha

            content = decode_content(data)

            task = content.get("task", "").strip()
            if not task:
                log("task フィールドが空です。スキップします。")
                time.sleep(POLL_INTERVAL)
                continue

            requested_by = content.get("requested_by", "unknown")
            timestamp    = content.get("timestamp", "")
            log(f"タスク受信 by={requested_by} ts={timestamp}")

            if not git_pull():
                log("git pull 失敗のため今回はスキップします。")
                time.sleep(POLL_INTERVAL)
                continue

            run_claude(task)
            clear_inbox()

        except KeyboardInterrupt:
            log("停止しました。")
            sys.exit(0)
        except Exception as e:
            log(f"予期しないエラー: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
