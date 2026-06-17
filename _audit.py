from db import get_conn
conn = get_conn()

print("=== 各來源 summarized 文章數與平均分 ===")
rows = conn.execute("""
    SELECT a.source, f.category, COUNT(*) as cnt,
           ROUND(AVG(a.relevance_score),1) as avg_score,
           MIN(a.relevance_score) as min_score
    FROM articles a JOIN feeds f ON a.source=f.name
    WHERE a.status='summarized'
    GROUP BY a.source
    ORDER BY f.category, avg_score DESC
""").fetchall()
for r in rows:
    print(f"  [{r['category']}] {r['source']}: {r['cnt']}篇  avg={r['avg_score']}  min={r['min_score']}")

print()
print("=== summarized 裡分類為「其他」的文章（可能 AI 無關）===")
rows2 = conn.execute("""
    SELECT a.title, a.source, a.relevance_score
    FROM articles a
    WHERE a.status='summarized' AND a.content_category='其他'
    ORDER BY a.relevance_score ASC
    LIMIT 20
""").fetchall()
for r in rows2:
    print(f"  [{r['relevance_score']}分] {r['source']} | {r['title'][:65]}")

print()
print("=== 各狀態總數 ===")
for r in conn.execute("SELECT status, COUNT(*) as cnt FROM articles GROUP BY status").fetchall():
    print(f"  {r['status']}: {r['cnt']}")

print()
print("=== 停用/無效的 feeds ===")
for r in conn.execute("SELECT name, category, active FROM feeds ORDER BY category").fetchall():
    status = "✓" if r['active'] else "✗ 停用"
    print(f"  {status}  [{r['category']}] {r['name']}")
conn.close()
