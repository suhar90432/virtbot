import db

with db.connect() as c:
    for table in ("promo_uses", "promos", "reviews", "referrals", "orders", "topups", "settings"):
        c.execute(f"DELETE FROM {table}")
    c.execute("DELETE FROM users WHERE tg_id<>8311462656")
    c.execute("UPDATE users SET balance=0, referrer_id=NULL WHERE tg_id=8311462656")

print("stats:", db.stats())
print("reviews:", db.review_summary())
print("users:", db.all_user_ids())
