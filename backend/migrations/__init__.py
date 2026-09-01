# 数据库迁移脚本目录
# 启动时 init_db() 会按 ALL_MIGRATIONS 顺序自动运行（全部幂等）。
# 也可单独运行: python -m backend.migrations.migrate_xxx
from . import (
    migrate_add_columns,
    migrate_add_is_enabled,
    migrate_add_prompt_columns,
    migrate_add_speaker_detection_columns,
    migrate_add_user_id,
    migrate_add_veto,
    migrate_drop_compatibility_mode,
    migrate_rule_ids_to_json,
)

# 顺序：先列变更，后数据迁移
ALL_MIGRATIONS = (
    migrate_add_columns,
    migrate_add_is_enabled,
    migrate_add_prompt_columns,
    migrate_add_speaker_detection_columns,
    migrate_add_user_id,
    migrate_add_veto,
    migrate_drop_compatibility_mode,
    migrate_rule_ids_to_json,
)
