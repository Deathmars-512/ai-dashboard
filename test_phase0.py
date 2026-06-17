import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=== Phase 0 驗收測試 ===\n")

# 測試 1：套件 import
print("[1] 檢查套件...")
try:
    import feedparser
    import trafilatura
    import ollama
    print("    feedparser / trafilatura / ollama OK")
except ImportError as e:
    print(f"    FAIL 套件缺失：{e}")
    sys.exit(1)

# 測試 2：Ollama 服務連線
print("[2] 連線 Ollama 服務（localhost:11434）...")
try:
    models = ollama.list()
    names = [m.model for m in models.models]
    print(f"    已安裝模型：{names}")
    qwen_found = any("qwen3" in n for n in names)
    if qwen_found:
        print("    qwen3 OK")
    else:
        print("    FAIL 找不到 qwen3，請確認 ollama pull qwen3:8b 已完成")
        sys.exit(1)
except Exception as e:
    print(f"    FAIL 無法連線 Ollama：{e}")
    sys.exit(1)

# 測試 3：簡單呼叫 Qwen
print("[3] 呼叫 Qwen3 做一句中文回應（約 10 秒）...")
try:
    resp = ollama.chat(
        model="qwen3:8b",
        messages=[{"role": "user", "content": "用一句繁體中文回答：你是誰？"}],
        options={"num_predict": 50},
    )
    reply = resp.message.content.strip()
    print(f"    Qwen 回應：{reply}")
    print("    qwen3 呼叫 OK")
except Exception as e:
    print(f"    FAIL 呼叫失敗：{e}")
    sys.exit(1)

print("\n=== Phase 0 全部通過，可以開始 Phase 1 ===")
