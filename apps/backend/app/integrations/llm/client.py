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
        """Send a multimodal request with images and text prompt."""
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

    async def analyze_page_structure(
        self,
        screenshot_bytes: bytes,
        page_source_xml: str,
    ) -> dict[str, Any]:
        """Analyze a mobile page using both screenshot and XML page source.

        The screenshot is submitted as an image, and the XML page source
        content is directly embedded in the prompt text.

        Args:
            screenshot_bytes: PNG bytes of the screenshot.
            page_source_xml: Raw XML string of the page source hierarchy.
        """
        start_time = time.time()

        # Truncate very large XML to avoid exceeding token limits.
        # Most page sources are under 50k chars; if larger, keep the first
        # portion which usually contains the most relevant structure.
        max_xml_chars = 60000
        xml_truncated = False
        xml_content = page_source_xml
        if len(xml_content) > max_xml_chars:
            xml_content = xml_content[:max_xml_chars]
            xml_truncated = True

        truncation_note = ""
        if xml_truncated:
            truncation_note = "\n（注意：XML 内容因长度过大已截断，请基于已提供的部分进行分析）\n"

        prompt_text = f"""你是移动端测试与UI结构分析专家。

我将提供：
1. 页面截图（以图片形式附上）
2. Android/iOS 页面 XML 源码（直接附在下方）
{truncation_note}
【页面 XML 源码】
```xml
{xml_content}
```

请严格基于这两项内容分析，不得臆测不存在的功能。
必须同时分析截图中的图片文字内容。
必须区分：
- XML中的结构文字
- 截图中的视觉文字（OCR可见文字）

如存在不一致或异常，必须列出。

--------------------------------
【分析任务】
--------------------------------

1️⃣ 判断页面类型及核心功能（简洁说明）

2️⃣ 提取页面结构分区
如：
- 顶部区
- 内容区
- 按钮区
- 底部导航区
如无法判断标记 "unknown"

3️⃣ 提取所有可交互元素
每个元素需包含：
- element_type
- display_text
- resource_id
- content_desc
- clickable (true/false)
- 推荐定位方式（优先级：id > content-desc > text > xpath）
- 定位稳定性评估（stable / unstable / risky）

4️⃣ 文案问题分析（区分来源）
- XML文字问题
- 图片视觉文字问题
检查：
- 错别字
- 语义不清
- 多语言混乱
- 文案不一致

5️⃣ 页面潜在问题分析
- 点击区域异常
- 不合理布局
- 层级过深（>12）
- 重复clickable嵌套
- 元素遮挡
- 视觉与结构不一致
- 潜在交互风险

6️⃣ 测试建议
- 必测功能点
- 风险验证点

--------------------------------
【界面评分逻辑】
--------------------------------

基于上述分析结果，进行客观扣分评分。

四个评分维度：

① structure_score（结构质量 0-100）
扣分项：
- 层级>12
- 冗余嵌套
- 空容器
- 结构异常

② copy_score（文案质量 0-100）
扣分项：
- 错别字
- 语义不清
- 多语言混乱
- XML与截图文字不一致

③ visual_score（视觉合理性 0-100）
扣分项：
- 主按钮不突出
- 遮挡
- 文字裁切
- 布局明显失衡

④ interaction_score（交互完整性 0-100）
扣分项：
- 缺少主操作
- 缺少返回路径
- 存在死角页面
- 交互路径不完整

--------------------------------
【评分规则】

- 初始分100
- 每发现明确问题合理扣分
- 必须基于XML或截图中的客观事实
- 不允许主观表达
- 若信息不足，该项给80分并标记"information_insufficient"
- 分数必须为整数

--------------------------------
【总分计算】

total_score =
structure_score × 25%
+ copy_score × 25%
+ visual_score × 25%
+ interaction_score × 25%

结果四舍五入取整数。

--------------------------------
【风险等级】

- total_score ≥ 85 → low
- 70 ≤ total_score < 85 → medium
- total_score < 70 → high

--------------------------------
【输出格式（必须严格JSON）】

{{
  "page_type": "",
  "page_summary": "",
  "layout_sections": [],
  "interactive_elements": [],
  "copy_issues": {{
    "xml_text_issues": [],
    "image_text_issues": [],
    "inconsistencies": []
  }},
  "potential_issues": [],
  "test_recommendations": [],
  "scores": {{
    "structure_score": 0,
    "copy_score": 0,
    "visual_score": 0,
    "interaction_score": 0,
    "total_score": 0
  }},
  "risk_level": "low | medium | high"
}}

--------------------------------
如果无法确认，请标记为 "unknown"。
只允许输出JSON，不得输出额外解释文字。"""

        try:
            output_text = await self._create_multimodal_response_text(
                images=[screenshot_bytes],
                prompt_text=prompt_text,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            import json

            # Strip markdown code fences if the model wraps the response
            cleaned = output_text.strip()
            if cleaned.startswith("```"):
                first_newline = cleaned.index("\n")
                cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].rstrip()

            try:
                result_json = json.loads(cleaned)
            except json.JSONDecodeError:
                result_json = {"raw_response": output_text}

            return {
                "success": True,
                "analysis_type": "page_structure",
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
                "confidence": 0.90,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "analysis_type": "page_structure",
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
