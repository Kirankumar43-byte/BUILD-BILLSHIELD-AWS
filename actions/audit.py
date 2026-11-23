"""SQLite storage: audit log, settings, fix-plan progress."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
import config


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, "
              "action TEXT, target TEXT, mode TEXT, result TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS plan(fid TEXT PRIMARY KEY, done INTEGER)")
    return c


def init():
    with closing(_conn()):
        pass


def log(action, target, mode, result):
    with closing(_conn()) as c:
        c.execute("INSERT INTO audit(ts,action,target,mode,result) VALUES(?,?,?,?,?)",
                  (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), action, target, mode, result))
        c.commit()


def logs():
    with closing(_conn()) as c:
        return c.execute("SELECT ts,action,target,mode,result FROM audit ORDER BY id DESC").fetchall()


def get_setting(k, default=""):
    with closing(_conn()) as c:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def set_setting(k, v):
    with closing(_conn()) as c:
        c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (k, str(v)))
        c.commit()


def plan_done():
    with closing(_conn()) as c:
        return {r[0] for r in c.execute("SELECT fid FROM plan WHERE done=1")}


def plan_set(fid, done):
    with closing(_conn()) as c:
        c.execute("INSERT OR REPLACE INTO plan(fid,done) VALUES(?,?)", (fid, int(done)))
        c.commit()
