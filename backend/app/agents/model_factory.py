"""
Model 层工厂（Model Factory）- 统一管理 LangChain ChatModel 实例

模块职责：
    提供统一的模型创建入口，支持两种模型类型：
    - ChatModel: 文本对话模型（支持 tool calling，用于 orchestrator）
    - VisionModel: 多模态视觉分析模型（用于画面深度理解）

配置来源：
    所有模型参数从 .env 文件读取：
    - LLM_API_KEY: API 密钥
    - LLM_BASE_URL: API 基础 URL（支持自定义端点）
    - LLM_MODEL_NAME: 对话模型名称
    - LLM_VISION_MODEL: 视觉模型名称（默认与对话模型相同）
"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()


class ModelFactory:
    """
    ChatModel 工厂单例，提供对话模型和视觉模型的统一创建接口。

    设计模式：
        采用单例模式（__new__），确保全局只有一个 ModelFactory 实例，
        避免重复创建模型实例造成的资源浪费。
    """

    _instance: Optional["ModelFactory"] = None
    _chat_model: Optional[ChatOpenAI] = None
    _vision_model: Optional[ChatOpenAI] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ==================== 配置属性 ====================
    # 以下属性均从 .env 文件读取，提供默认值以确保应用可启动

    @property
    def api_key(self) -> str:
        """获取 LLM API 密钥"""
        return os.getenv("LLM_API_KEY", "sk-xxx")

    @property
    def base_url(self) -> str:
        """获取 LLM API 基础 URL（支持自定义端点，如代理服务器）"""
        return os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

    @property
    def model_name(self) -> str:
        """获取对话模型名称（如 gpt-4o、qwen-max 等）"""
        return os.getenv("LLM_MODEL_NAME", "gpt-4o")

    @property
    def vision_model_name(self) -> str:
        """获取视觉模型名称，默认与对话模型相同"""
        return os.getenv("LLM_VISION_MODEL", self.model_name)

    # ==================== Chat Model ====================

    def get_chat_model(
        self,
        temperature: float = 0.3,
        streaming: bool = True,
        bind_tools: Optional[list] = None,
    ) -> ChatOpenAI:
        """
        获取文本对话模型（支持 tool calling）。

        用于 orchestrator 的 ReAct 循环，低 temperature 确保
        工具选择稳定、回复确定性高。

        Args:
            temperature: 温度参数（float，0.0-2.0），越低越确定
            streaming: 是否启用流式输出（bool），Phase 2 为 True
            bind_tools: 可选的 tool 列表（List[BaseTool]），
                绑定到模型后 LLM 可自主选择调用

        Returns:
            ChatOpenAI 实例，若传入 bind_tools 则返回绑定了工具的模型
        """
        # 每次创建新实例，避免不同请求间的 streaming 配置冲突
        model = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            streaming=streaming,
        )
        if bind_tools:
            # 将工具绑定到模型，使 LLM 能够通过 tool_calls 调用工具
            model = model.bind_tools(bind_tools)
        return model

    # ==================== Vision Model ====================

    def get_vision_model(
        self,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> ChatOpenAI:
        """
        获取视觉分析模型（用于多模态图片分析）。

        使用更低的 temperature（0.1）确保分析结果稳定，
        max_tokens 限制输出长度避免冗余。

        Args:
            temperature: 温度参数（float），默认 0.1（高确定性）
            max_tokens: 最大输出 token 数（int），默认 1000

        Returns:
            ChatOpenAI 实例（多模态模型）
        """
        return ChatOpenAI(
            model=self.vision_model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# 全局单例：供 orchestrator、vision_agent、llm_service 调用
model_factory = ModelFactory()
