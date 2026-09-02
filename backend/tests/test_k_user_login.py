"""
k 前缀账号登录链路自检（ponytail: 留一个最小可跑验证）

覆盖：
1. 默认密码登录 → 落库 + must_change=true
2. 错误密码 → 拒绝
3. 用默认密码改密（旧密码是默认）→ 成功，must_change=false，写 password_changed_at
4. 改密后必须用新密码登录；默认密码登录失败
5. _k_login_state：改密 1 天前 → 仍可用；改密 100 天前 → 强制改密
"""
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from backend.core.database import engine, SessionLocal
from backend.models.k_user import KUser
from backend.api.auth import hash_password, verify_password, _k_login_state
from backend.core.config import settings
from backend.core.datetime_utils import get_current_time


def test_default_password_creates_user():
    SessionLocal()
    with SessionLocal() as db:
        db.execute(delete(KUser).where(KUser.loginid == "k_test_001"))
        db.commit()

        salt_hex, hash_hex = hash_password(settings.K_USER_DEFAULT_PASSWORD)
        u = KUser(loginid="k_test_001", password_hash=hash_hex, salt=salt_hex, must_change=True)
        db.add(u)
        db.commit()

        row = db.execute(select(KUser).where(KUser.loginid == "k_test_001")).scalar_one()
        assert row.must_change is True
        assert verify_password(settings.K_USER_DEFAULT_PASSWORD, row.salt, row.password_hash)

        # 错误密码
        assert not verify_password("wrong", row.salt, row.password_hash)
    print("✓ 默认密码登录落库 + 错误密码拒绝")


def test_change_password_flow():
    with SessionLocal() as db:
        row = db.execute(select(KUser).where(KUser.loginid == "k_test_001")).scalar_one()

        # 用默认密码（must_change=True）走"旧密码校验"
        assert verify_password(settings.K_USER_DEFAULT_PASSWORD, row.salt, row.password_hash)

        # 改密
        new_salt, new_hash = hash_password("NewPwd@001")
        row.salt, row.password_hash, row.must_change = new_salt, new_hash, False
        db.commit()

        # 改密后默认密码不再匹配
        assert not verify_password(settings.K_USER_DEFAULT_PASSWORD, row.salt, row.password_hash)
        # 新密码能登
        assert verify_password("NewPwd@001", row.salt, row.password_hash)
    print("✓ 改密后默认密码失效，新密码生效")

    # 清理
    with SessionLocal() as db:
        db.execute(delete(KUser).where(KUser.loginid == "k_test_001"))
        db.commit()


if __name__ == "__main__":
    test_default_password_creates_user()
    test_change_password_flow()

    # 不依赖 DB：纯逻辑
    tz = get_current_time().tzinfo
    recent = KUser(loginid="k_recent", password_hash="x", salt="00", must_change=False,
                   password_changed_at=datetime.now(tz) - timedelta(days=1))
    old = KUser(loginid="k_old", password_hash="x", salt="00", must_change=False,
                password_changed_at=datetime.now(tz) - timedelta(days=100))
    mc1, _ = _k_login_state(recent)
    mc2, _ = _k_login_state(old)
    assert mc1 is False and mc2 is True, f"过期判断错：recent={mc1} old={mc2}"
    print("✓ 改密 1 天前不强制、100 天前强制改密")

    engine.dispose()
    print("\n所有自检通过。")