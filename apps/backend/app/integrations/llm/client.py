"""LLM client integration for AI-powered analysis."""
import base64
import time
from typing import Any, Optional

from openai import AsyncOpenAI

from app.core.config import settings


class LLMClient:
    """LLM client for AI-powered screenshot and test analysis."""

    def __init__(self):
        client_kwargs: dict[str, Any] = {}
        if settings.llm_base_url:
            client_kwargs["base_url"] = settings.llm_base_url

        self._client = AsyncOpenAI(api_key=settings.openai_api_key, **client_kwargs)
        self.model = settings.openai_model
        self.timeout = settings.ai_analysis_timeout

    def _png_data_url(self, png_bytes: bytes) -> str:
        image_base64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{image_base64}"

    async def _create_multimodal_response_text(self, images: list[bytes], prompt_text: str) -> str:
        import json as _json

        images_urls = [self._png_data_url(b) for b in images]

        responses_api = getattr(self._client, "responses", None)
        if responses_api and hasattr(responses_api, "create"):
            content = [{"type": "input_image", "image_url": u} for u in images_urls]
            content.append({"type": "input_text", "text": prompt_text})
            response = await responses_api.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                timeout=self.timeout,
            )
            output_text = getattr(response, "output_text", None)
            if output_text:
                return output_text
            return _json.dumps(response.model_dump(), ensure_ascii=False)

        content = [{"type": "image_url", "image_url": {"url": u}} for u in images_urls]
        content.append({"type": "text", "text": prompt_text})
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            timeout=self.timeout,
        )
        message = response.choices[0].message
        return message.content or _json.dumps(response.model_dump(), ensure_ascii=False)

    async def analyze_screenshot(
        self,
        screenshot_bytes: bytes,
        analysis_type: str = "ui_state",
        additional_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze a screenshot using vision model."""
        start_time = time.time()

        prompts = {
            "ui_state": """请分析这张移动端 App 截图，并用中文描述：
1. 当前页面类型（如：登录页、首页、设置页等）
2. 关键可见 UI 元素（按钮、输入框、列表、提示文案等）
3. App 的状态（如：加载中、错误态、成功态等）
4. 可操作元素及其大致位置

请严格以 JSON 输出，键名必须保持为英文：screen_type, elements, state, actionable_items；键值内容用中文。""",
            "anomaly": """请检查这张移动端 App 截图是否存在潜在问题，并用中文给出结论：
1. UI 渲染问题（重叠、截断、遮挡等）
2. 布局问题（对齐/间距异常等）
3. 图片缺失或破损
4. 可用性/无障碍相关问题
5. 其他可疑的视觉异常或缺陷

请严格以 JSON 输出，键名必须保持为英文：has_anomaly, anomalies, severity, summary；键值内容用中文。""",
            "element_detect": """请识别截图中所有可交互的 UI 元素，并用中文描述元素信息：
1. 按钮及其文案
2. 文本输入框
3. 可点击链接或文本
4. 开关、复选框、单选框等
5. 导航元素

每个元素请给出：type, label, approximate_location（top/middle/bottom + left/center/right）。

请严格以 JSON 输出，键名必须保持为英文：elements；键值内容用中文。""",
        }

        prompt_text = prompts.get(analysis_type, prompts["ui_state"])
        if additional_context:
            prompt_text += f"\n\n补充上下文（中文）：{additional_context}"

        try:
            latency_ms = int((time.time() - start_time) * 1000)
            output_text = await self._create_multimodal_response_text([screenshot_bytes], prompt_text)

            import json

            try:
                result_json = json.loads(output_text)
            except json.JSONDecodeError:
                result_json = {"raw_response": output_text}

            return {
                "success": True,
                "analysis_type": analysis_type,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
                "confidence": 0.85,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "analysis_type": analysis_type,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
                "confidence": 0.0,
            }

    async def compare_screenshots(
        self,
        baseline_bytes: bytes,
        target_bytes: bytes,
    ) -> dict[str, Any]:
        """Compare two screenshots for visual differences."""
        start_time = time.time()

        prompt = """请对比两张移动端 App 截图（第一张为基线，第二张为当前）并用中文输出差异：
1. 找出两者的视觉差异
2. 将变化分类为：layout_change, text_change, color_change, element_added, element_removed, other
3. 评估变化的重要程度：minor, moderate, significant
4. 判断变化是否更像是正常改动还是潜在缺陷

请严格以 JSON 输出，键名必须保持为英文：differences, overall_similarity, risk_level, summary；键值内容用中文。"""

        try:
            latency_ms = int((time.time() - start_time) * 1000)
            output_text = await self._create_multimodal_response_text([baseline_bytes, target_bytes], prompt)

            import json

            try:
                result_json = json.loads(output_text)
            except json.JSONDecodeError:
                result_json = {"raw_response": output_text}

            return {
                "success": True,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
            }

    async def generate_test_suggestion(
        self,
        screenshot_bytes: bytes,
        current_test_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate test step suggestions based on current screen."""
        start_time = time.time()

        prompt = """请根据这张移动端 App 截图，建议下一步测试动作（用中文描述）：
1. 当前可交互元素有哪些？
2. 从这个页面出发，合理的测试步骤是什么？
3. 建议做哪些断言？

请严格以 JSON 输出，键名必须保持为英文：
- suggested_actions（list，元素结构为 {action, target, description}）
- suggested_assertions（list，元素结构为 {type, target, expected}）
- navigation_options（list）
键值内容用中文。"""

        if current_test_context:
            prompt += f"\n\n当前测试上下文（中文）：{current_test_context}"

        try:
            latency_ms = int((time.time() - start_time) * 1000)
            output_text = await self._create_multimodal_response_text([screenshot_bytes], prompt)

            import json

            try:
                result_json = json.loads(output_text)
            except json.JSONDecodeError:
                result_json = {"raw_response": output_text}

            return {
                "success": True,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
            }


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
