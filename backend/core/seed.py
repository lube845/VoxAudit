"""
初始化数据脚本 - 创建默认规则
"""
import asyncio

from backend.core.database import AsyncSessionLocal
from backend.models.rule import ScoringRule


async def seed_data():
    """创建初始数据"""
    async with AsyncSessionLocal() as db:
        # 检查是否已有数据
        from sqlalchemy import select
        result = await db.execute(select(ScoringRule))
        if result.scalars().first():
            print("数据已存在，跳过初始化")
            return

        # 创建示例规则（归属admin用户）
        rule1 = ScoringRule(
            name="服务态度良好",
            code="bonus_service_attitude",
            version="v_250509000001",
            description="坐席服务态度热情友好，及时响应客户需求",
            total_score=10,
            rule_type="bonus",
            is_latest=True,
            user_id="admin",
        )
        db.add(rule1)

        rule2 = ScoringRule(
            name="未核实客户身份",
            code="deduction_verify_identity",
            version="v_250509000002",
            description="坐席未按流程核实客户身份信息",
            total_score=5,
            rule_type="deduction",
            is_latest=True,
            user_id="admin",
        )
        db.add(rule2)

        await db.commit()
        print("初始化数据创建成功!")


if __name__ == "__main__":
    asyncio.run(seed_data())