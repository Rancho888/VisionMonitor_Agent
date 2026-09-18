"""
大模型服务 - 多模态视觉分析模块

核心职责:
    1. 提供通用图片分析能力（analyze_image），供 Agent 工具链调用
    2. 提供人脸比对能力（compare_faces），通过多模态视觉模型判断监控画面中的人物身份

设计说明:
    - 文本对话已由 orchestrator.py 中的 LangChain Agent 接管，本模块仅保留多模态视觉分析能力
    - 通过 model_factory 获取视觉模型实例，解耦模型配置与分析逻辑
    - 采用 HumanMessage + image_url 方式构建多模态消息，兼容 OpenAI / 通义 / 智谱等主流视觉模型

依赖关系:
    - backend.app.agents.model_factory: 模型工厂，提供 get_vision_model()
    - langchain_core.messages.HumanMessage: LangChain 消息抽象
"""
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from backend.app.agents.model_factory import model_factory


class LLMService:
    """
    视觉分析服务（基于多模态大模型）

    核心职责:
        - 通用图片分析: 对监控截图进行场景描述、异常检测等
        - 人脸比对: 将监控画面中的人脸与参考人像进行 1:1 比对

    使用方式:
        通过全局单例 llm_service 调用，例如:
            result = await llm_service.compare_faces(monitor_b64, ref_b64, "张三")

    设计模式:
        - 无状态设计，所有配置通过 model_factory 获取
        - 异步接口，适配 FastAPI 的 async 调用链
    """

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
    ) -> str:
        """
        使用视觉模型分析单张图片

        功能:
            将 base64 编码的图片与文本提示组合为多模态消息，
            调用视觉模型进行分析，返回模型的文本描述。

        参数:
            image_base64: JPEG 图片的 base64 编码字符串
            prompt: 分析提示词，描述希望模型关注的分析维度

        返回:
            str: 模型的分析结果文本

        异常:
            若模型调用失败，异常将向上抛出由调用方处理

        多模态消息构建说明:
            - 采用 text + image_url 交替排列的方式构建消息
            - image_url 使用 data URI 内联 base64，避免外部链接依赖
            - 此格式兼容 OpenAI GPT-4o / 通义千问VL / 智谱GLM-4V 等主流视觉模型
        """
        model = model_factory.get_vision_model()

        # 构建多模态消息：文本提示 + 内联 base64 图片
        # data URI 格式 (data:image/jpeg;base64,...) 兼容各视觉模型 API
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                },
            ]
        )

        response = await model.ainvoke([message])
        return response.content

    async def compare_faces(
        self,
        monitor_image_base64: str,
        reference_image_base64: str,
        reference_name: str,
    ) -> Dict[str, Any]:
        """
        使用视觉模型比对两张人脸（1:1 人脸验证）

        功能:
            将参考人像与监控画面中的人脸进行视觉比对，判断是否为同一人，
            并输出置信度评分。

        参数:
            monitor_image_base64: 监控画面截图的 base64 编码
            reference_image_base64: 参考人像（注册照片）的 base64 编码
            reference_name: 参考人像对应的姓名，用于提示词引导模型关注

        返回:
            Dict[str, Any]: {
                "is_match": bool,      # 是否匹配（模型判断结果）
                "confidence": float,   # 置信度 0.0~1.0
                "raw_response": str,   # 模型原始返回文本
            }

        异常:
            - 解析模型输出失败时，confidence 回退为 0.5（保守策略）

        max_tokens=200 选择理由:
            人脸比对仅需输出 "是/否,置信度" 的简短文本，200 tokens 足够，
            可有效防止模型输出冗余内容，加速推理。
        """
        # 限制 max_tokens=200：比对任务输出极短，防止模型生成冗余内容，加速推理
        model = model_factory.get_vision_model(max_tokens=200)

        # ---- 结构化人脸比对提示词 ----
        # 设计要点:
        #   1. 角色定义：明确模型作为"人脸比对专家"的身份，引导专业判断
        #   2. 判断维度：列出面部特征、轮廓、五官等具体比对维度，避免笼统判断
        #   3. 输出约束：严格限定输出格式为 "是/否,置信度"，便于程序化解析
        #   4. 防幻觉：强调"仅根据视觉特征判断"，减少模型臆测
        prompt = (
            f"你是一位专业的人脸比对专家，擅长通过视觉特征判断两张照片中是否为同一人。\n\n"
            f"## 参考人像\n"
            f"姓名: {reference_name}\n\n"
            f"## 监控画面\n"
            f"请仔细观察监控画面中的人脸。\n\n"
            f"## 判断维度\n"
            f"请从以下维度综合比对：\n"
            f"1. 面部整体轮廓（脸型、下颌线、额头比例）\n"
            f"2. 五官特征（眼睛形状与间距、鼻梁形态、嘴唇厚度与形状）\n"
            f"3. 面部细节（眉毛弧度、耳朵轮廓、肤色与纹理）\n"
            f"4. 整体气质与比例（面部宽高比、对称性）\n\n"
            f"## 注意事项\n"
            f"- 监控画面可能存在角度偏差、光照差异、遮挡等情况，请综合考虑\n"
            f"- 仅根据视觉特征进行判断，不要臆测\n\n"
            f"## 输出格式\n"
            f"严格按以下格式输出，不要添加任何额外内容：\n"
            f"是,<置信度>  或  否,<置信度>\n"
            f"其中置信度为 0-100 的整数，表示你对判断的确信程度。\n"
            f"示例：是,85  或  否,30"
        )

        # 多模态消息构建：参考人像 + 监控画面 + 比对指令
        # 图片顺序与提示词中的"参考人像→监控画面"对应，帮助模型建立清晰的比对上下文
        message = HumanMessage(
            content=[
                {"type": "text", "text": f"参考人像（{reference_name}）："},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{reference_image_base64}"},
                },
                {"type": "text", "text": "监控画面中的人："},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{monitor_image_base64}"},
                },
                {"type": "text", "text": prompt},
            ]
        )

        response = await model.ainvoke([message])
        content = response.content.strip()

        # ---- 解析模型输出 ----
        # 解析策略：
        #   - 以"是"开头判断为匹配，否则为不匹配
        #   - 逗号分隔取第二段作为置信度，除以 100 归一化到 0~1
        #   - 解析失败时回退为 0.5（保守策略，避免误判）
        is_match = content.startswith("是")
        try:
            confidence = float(content.split(",")[1]) / 100 if "," in content else 0.5
        except (IndexError, ValueError):
            confidence = 0.5

        return {
            "is_match": is_match,
            "confidence": confidence,
            "raw_response": content,
        }


# 全局单例 —— 供其他模块直接 import 使用，避免重复实例化
llm_service = LLMService()
