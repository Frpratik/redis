"""
Redis first 5 data types in Python (redis-py).

Setup:
    pip install redis
    Make sure a Redis server is running on localhost:6379
    (on Windows: use Docker `docker run -p 6379:6379 redis` or WSL)

Run:
    python redis_first_5_types.py

Every key starts with "demo:" and is deleted at the start and the end,
so running this file never touches your other Redis data.
"""

import time
import redis

# decode_responses=True -> get normal Python str back instead of bytes
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


def show(title, value):
    """Small helper to print results neatly."""
    print(f"{title:<45} -> {value}")


def cleanup():
    """Delete only our own demo keys (SCAN is safe, KEYS is not for production)."""
    for key in r.scan_iter(match="demo:*", count=100):
        r.delete(key)


# ---------------------------------------------------------------
# 1. STRING: one value (cache, OTP, counter)
# ---------------------------------------------------------------
def string_demo():
    print("\n=== 1. STRING ===")

    r.set("demo:name", "Ravi")                         # SET name "Ravi"
    show("GET name", r.get("demo:name"))               # "Ravi"

    r.set("demo:otp:9876", "4821", ex=60)              # SET ... EX 60 (auto-delete in 60 sec)
    show("TTL otp (seconds left)", r.ttl("demo:otp:9876"))   # -2 = gone, -1 = no expiry

    # SETNX: set only if key does NOT exist (True = set, False = already there)
    show("SETNX lock (first time)", r.setnx("demo:lock:order1", "yes"))
    show("SETNX lock (second time)", r.setnx("demo:lock:order1", "yes"))

    # Counters (atomic, safe with many clients)
    r.set("demo:views", 0)
    show("INCR views", r.incr("demo:views"))           # 1
    show("INCR views", r.incr("demo:views"))           # 2
    show("INCRBY views 10", r.incrby("demo:views", 10))  # 12
    show("DECR views", r.decr("demo:views"))           # 11

    show("APPEND name ' Ghuge'", r.append("demo:name", " Ghuge"))  # returns new length
    show("GET name", r.get("demo:name"))               # "Ravi Ghuge"
    show("STRLEN name", r.strlen("demo:name"))

    r.mset({"demo:a": 1, "demo:b": 2, "demo:c": 3})    # MSET a 1 b 2 c 3
    show("MGET a b c", r.mget(["demo:a", "demo:b", "demo:c"]))

    show("EXISTS name", r.exists("demo:name"))         # 1
    r.expire("demo:views", 300)                        # add expiry to existing key
    show("TTL views", r.ttl("demo:views"))
    show("DEL name", r.delete("demo:name"))            # 1 = deleted
    show("EXISTS name", r.exists("demo:name"))         # 0


# ---------------------------------------------------------------
# 2. LIST: ordered line, duplicates allowed (queue, latest N)
# ---------------------------------------------------------------
def list_demo():
    print("\n=== 2. LIST ===")

    r.rpush("demo:queue", "email", "report")           # add to RIGHT -> [email, report]
    r.lpush("demo:queue", "urgent")                    # add to LEFT  -> [urgent, email, report]
    show("LRANGE queue 0 -1 (all)", r.lrange("demo:queue", 0, -1))
    show("LRANGE queue 0 1 (first two)", r.lrange("demo:queue", 0, 1))
    show("LLEN queue", r.llen("demo:queue"))           # 3
    show("LINDEX queue 0", r.lindex("demo:queue", 0))  # "urgent"

    show("LPOP queue (remove from left)", r.lpop("demo:queue"))    # "urgent"
    show("RPOP queue (remove from right)", r.rpop("demo:queue"))   # "report"

    # BLPOP: wait up to 2 sec for an item (worker style). Returns (key, value) or None.
    show("BLPOP queue 2", r.blpop("demo:queue", timeout=2))        # ("demo:queue", "email")
    show("BLPOP on empty queue (waits 1 sec)", r.blpop("demo:queue", timeout=1))  # None

    # Queue rule: RPUSH + LPOP = first in, first out (queue)
    #             LPUSH + LPOP = last in, first out (stack)

    # Story: always keep only the newest 5 notifications
    for i in range(1, 9):
        r.lpush("demo:notif:1", f"notification {i}")
        r.ltrim("demo:notif:1", 0, 4)                  # keep first 5 only
    show("Latest 5 notifications", r.lrange("demo:notif:1", 0, -1))

    r.rpush("demo:dups", "x", "y", "x")
    show("LREM dups 1 'x' (remove 1 occurrence)", r.lrem("demo:dups", 1, "x"))
    show("List after LREM", r.lrange("demo:dups", 0, -1))


# ---------------------------------------------------------------
# 3. SET: unique only, no order (unique visitors, tags, likes)
# ---------------------------------------------------------------
def set_demo():
    print("\n=== 3. SET ===")

    r.sadd("demo:skills", "python", "django", "python")    # duplicate ignored
    show("SMEMBERS skills", r.smembers("demo:skills"))     # {'python', 'django'}
    show("SISMEMBER skills 'django'", r.sismember("demo:skills", "django"))  # True
    show("SCARD skills (count)", r.scard("demo:skills"))   # 2
    show("SRANDMEMBER skills (random, keeps it)", r.srandmember("demo:skills"))
    show("SPOP skills (random, removes it)", r.spop("demo:skills"))
    show("SREM skills 'python' (remove)", r.srem("demo:skills", "python"))

    # Set math: the real power
    r.sadd("demo:ravi:friends", "asha", "neha", "karan")
    r.sadd("demo:asha:friends", "ravi", "neha", "karan")
    show("SINTER (in BOTH, mutual friends)",
         r.sinter("demo:ravi:friends", "demo:asha:friends"))
    show("SUNION (in EITHER)",
         r.sunion("demo:ravi:friends", "demo:asha:friends"))
    show("SDIFF (in first only)",
         r.sdiff("demo:ravi:friends", "demo:asha:friends"))

    # Story: post likes. Clicking twice still counts as 1 like.
    r.sadd("demo:likes:post1", "ravi")
    r.sadd("demo:likes:post1", "ravi")
    show("Total likes on post1", r.scard("demo:likes:post1"))   # 1


# ---------------------------------------------------------------
# 4. SORTED SET: unique + score, auto-sorted (leaderboard)
# ---------------------------------------------------------------
def sorted_set_demo():
    print("\n=== 4. SORTED SET ===")

    # redis-py takes a dict: {member: score}
    r.zadd("demo:board", {"Ravi": 500, "Asha": 800, "Neha": 650})
    show("ZRANGE (low -> high)", r.zrange("demo:board", 0, -1, withscores=True))
    show("ZREVRANGE (high -> low)", r.zrevrange("demo:board", 0, -1, withscores=True))
    show("Top 3 (ZREVRANGE 0 2)", r.zrevrange("demo:board", 0, 2))
    # Redis 6.2+ alternative: r.zrange("demo:board", 0, 2, desc=True)

    show("ZSCORE Ravi", r.zscore("demo:board", "Ravi"))        # 500.0
    show("ZRANK Ravi (low->high, starts at 0)", r.zrank("demo:board", "Ravi"))
    show("ZREVRANK Ravi (leaderboard rank)", r.zrevrank("demo:board", "Ravi"))
    show("ZCARD (count)", r.zcard("demo:board"))

    show("ZINCRBY Ravi +100", r.zincrby("demo:board", 100, "Ravi"))   # 600.0
    show("ZRANGEBYSCORE 600..800", r.zrangebyscore("demo:board", 600, 800))
    show("ZCOUNT 600..800", r.zcount("demo:board", 600, 800))
    show("ZREM Neha", r.zrem("demo:board", "Neha"))

    # Story: game leaderboard
    r.zadd("demo:game", {"Ravi": 0})
    r.zincrby("demo:game", 50, "Ravi")                 # scored 50
    r.zincrby("demo:game", 30, "Ravi")                 # scored 30 more -> 80
    show("Game top 3 with scores", r.zrevrange("demo:game", 0, 2, withscores=True))


# ---------------------------------------------------------------
# 5. HASH: mini dictionary (user profile, cart, session)
# ---------------------------------------------------------------
def hash_demo():
    print("\n=== 5. HASH ===")

    r.hset("demo:user:1", mapping={"name": "Ravi", "age": 28, "city": "Mumbai"})
    show("HGET name", r.hget("demo:user:1", "name"))
    show("HMGET name city", r.hmget("demo:user:1", ["name", "city"]))
    show("HGETALL", r.hgetall("demo:user:1"))
    show("HKEYS (field names)", r.hkeys("demo:user:1"))
    show("HVALS (values)", r.hvals("demo:user:1"))
    show("HLEN (number of fields)", r.hlen("demo:user:1"))
    show("HEXISTS city", r.hexists("demo:user:1", "city"))
    show("HINCRBY age +1", r.hincrby("demo:user:1", "age", 1))   # 29
    show("HDEL city", r.hdel("demo:user:1", "city"))
    show("HGETALL after HDEL", r.hgetall("demo:user:1"))

    # Story: shopping cart (product -> quantity)
    r.hset("demo:cart:1", mapping={"pen": 2, "book": 1})
    r.hincrby("demo:cart:1", "pen", 1)                 # pen is now 3
    r.hdel("demo:cart:1", "book")                      # remove book
    show("Cart", r.hgetall("demo:cart:1"))             # {'pen': '3'}


# ---------------------------------------------------------------
# COMMANDS THAT WORK ON ALL TYPES
# ---------------------------------------------------------------
def generic_demo():
    print("\n=== COMMANDS FOR ALL TYPES ===")

    show("TYPE of demo:name-like keys",
         {
             "demo:views": r.type("demo:views"),
             "demo:queue": r.type("demo:queue"),
             "demo:ravi:friends": r.type("demo:ravi:friends"),
             "demo:board": r.type("demo:board"),
             "demo:user:1": r.type("demo:user:1"),
         })

    # SCAN: safe way to find keys by pattern (KEYS blocks the server; avoid in production)
    show("SCAN match demo:user:*", list(r.scan_iter(match="demo:user:*", count=100)))

    r.set("demo:temp", "x", ex=60)
    show("TTL temp", r.ttl("demo:temp"))
    show("PERSIST temp (remove expiry)", r.persist("demo:temp"))
    show("TTL temp after PERSIST (-1 = no expiry)", r.ttl("demo:temp"))

    r.set("demo:short", "x", px=500)                   # PX = milliseconds
    time.sleep(1)
    show("EXISTS short after expiry", r.exists("demo:short"))   # 0

    # r.flushdb()  # DANGEROUS: deletes EVERYTHING in the current db. Left commented on purpose.


if __name__ == "__main__":
    r.ping()            # fails fast with ConnectionError if Redis is not running
    cleanup()
    string_demo()
    list_demo()
    set_demo()
    sorted_set_demo()
    hash_demo()
    generic_demo()
    cleanup()
    print("\nDone. All demo keys removed.")