"""
旧 ICP 接口适配层 —— 已迁移至 csp_service（4 步链路：generate → verify → query → decrypt）。

本文件保留仅为向后兼容：
  - 旧代码仍可直接 import IcpApiError / query_call_records
  - 行为已统一指向 csp_service（包含 MAC 鉴权）

新代码请直接 import backend.services.csp_service。
"""
from backend.services.csp_service import (
    CspApiError as IcpApiError,   # 让旧的 except IcpApiError 仍能捕获新错误
    query_call_records,
    ICP_SUCCESS_CODE,
    ICP_TRX_CODE,
)


__all__ = ["IcpApiError", "query_call_records", "ICP_SUCCESS_CODE", "ICP_TRX_CODE"]