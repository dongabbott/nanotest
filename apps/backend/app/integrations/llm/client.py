"""LLM client integration for AI-powered analysis.

Supports both text-only (e.g. qwen-plus) and vision-language (e.g. qwen-vl-max)
models via the OpenAI-compatible chat.completions API.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any, Optional

from openai import AsyncOpenAI

from app.core.config import settings


# ---------------------------------------------------------------------------
# Prompt library
# ---------------------------------------------------------------------------

VISION_SYSTEM_PROMPT = (
    "你是一位资深的移动端 App 测试与 UI 分析专家，擅长识别界面缺陷、"
    "布局问题和交互风险。请严格按照用户要求的 JSON 格式输出分析结果，"
    "不要输出任何额外解释文字。"
)

PROMPTS = {
    "ui_state": """请分析这张移动端 App 截图，并用中文描述：

1. 当前页面类型（如：登录页、首页、设置页、列表页、详情页等）
2. 关键可见 UI 元素（按钮、输入框、导航栏、列表项、提示文案、图标等）
3. App 的状态（加载中 / 错误态 / 空态 / 正常态 / 成功提示等）
4. 可操作元素及其大致位置（顶部/中部/底部 × 左/中/右）

严格以 JSON 输出，键名必须为英文：
```json
{
  "screen_type": "页面类型",
  "elements": [
    {"type": "元素类型", "label": "显示文字", "position": "top-left"}
  ],
  "state": "app状态",
  "actionable_items": [
    {"type": "button", "label": "按钮文字", "position": "bottom-center"}
  ]
}
```""",

    "anomaly": """请仔细检查这张移动端 App 截图是否存在潜在问题，并用中文给出结论：

检查维度：
1. UI 渲染问题（元素重叠、文字截断、图标遮挡、模糊/像素化）
2. 布局问题（对齐异常、间距不一致、元素溢出屏幕边界）
3. 图片/图标缺失或破损（占位符、空白区域、裂图图标）
4. 可用性问题（按钮过小、对比度不足、文字过小）
5. 状态栏/导航栏异常（时间/电量显示异常、返回按钮缺失）
6. 多语言问题（中英混排、乱码、未翻译文案）

严格以 JSON 输出：
```json
{
  "has_anomaly": true,
  "anomalies": [
    {"category": "渲染问题", "description": "描述", "location": "位置", "severity": "low|medium|high"}
  ],
  "severity": "low|medium|high",
  "summary": "一句话总结"
}
```
如果没有发现问题，has_anomaly 设为 false，anomalies 为空数组。""",

    "element_detect": """请识别截图中所有可交互的 UI 元素，并用中文描述：

识别范围：
1. 按钮（含文字按钮、图标按钮、浮动按钮）
2. 文本输入框 / 搜索框
3. 可点击链接或文本
4. 开关 / 复选框 / 单选框
5. 导航元素（返回、Tab栏、面包屑）
6. 列表项 / 卡片（可点击的）
7. 下拉菜单 / 选择器

严格以 JSON 输出：
```json
{
  "elements": [
    {
      "type": "button|input|link|switch|checkbox|tab|list_item|...",
      "label": "显示文字或图标描述",
      "approximate_location": "top-left|middle-center|bottom-right|...",
      "clickable": true
    }
  ]
}
```""",
}

PAGE_STRUCTURE_PROMPT = """你是移动端测试与 UI 结构分析专家。

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
- XML 中的结构文字
- 截图中的视觉文字（OCR 可见文字）

如存在不一致或异常，必须列出。

--------------------------------
【分析任务】
--------------------------------

1️⃣ 判断页面类型及核心功能（简洁说明）

2️⃣ 提取页面结构分区
如：顶部区、内容区、按钮区、底部导航区
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
- XML 文字问题
- 图片视觉文字问题
检查：错别字、语义不清、多语言混乱、文案不一致

5️⃣ 页面潜在问题分析
- 点击区域异常
- 不合理布局
- 层级过深（>12）
- 重复 clickable 嵌套
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
扣分项：层级>12、冗余嵌套、空容器、结构异常

② copy_score（文案质量 0-100）
扣分项：错别字、语义不清、多语言混乱、XML 与截图文字不一致

③ visual_score（视觉合理性 0-100）
扣分项：主按钮不突出、遮挡、文字裁切、布局明显失衡

④ interaction_score（交互完整性 0-100）
扣分项：缺少主操作、缺少返回路径、存在死角页面、交互路径不完整

--------------------------------
【评分规则】

- 初始分 100
- 每发现明确问题合理扣分
- 必须基于 XML 或截图中的客观事实
- 若信息不足，该项给 80 分并标记 "information_insufficient"
- 分数必须为整数

--------------------------------
【总分计算】

total_score = structure_score × 25% + copy_score × 25% + visual_score × 25% + interaction_score × 25%
结果四舍五入取整数。

--------------------------------
【风险等级】

- total_score ≥ 85 → low
- 70 ≤ total_score < 85 → medium
- total_score < 70 → high

--------------------------------
【输出格式（必须严格 JSON）】

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

如果无法确认，请标记为 "unknown"。
只允许输出 JSON，不得输出额外解释文字。"""

GENERATE_TEST_STEPS_PROMPT = """你是资深移动端自动化测试工程师。

我将提供：
1. 当前页面截图（以图片形式附上）
2. 页面 XML 源码（包含元素定位信息）
{truncation_note}
【页面 XML 源码】
```xml
{xml_content}
```

平台类型：{platform}
{scenario_context}

--------------------------------
【任务】
--------------------------------

基于截图和 XML 分析，自动生成可直接执行的自动化测试用例步骤。

--------------------------------
【生成规则】
--------------------------------

1. 步骤必须按用户操作流程排序（先看到什么→点击什么→输入什么→验证什么）
2. 每个步骤必须有明确的 UI 元素定位，优先使用 XML 中的精确定位器：
   - 最优：resource-id（strategy: "id"）
   - 次优：content-desc（strategy: "accessibility_id"）
   - 备选：text 属性（strategy: "xpath"，xpath 用 //*[text()="..."]）
   - 最后：xpath 绝对路径
3. 输入步骤的 text 字段应使用测试数据变量：
   - 邮箱：${{random_email()}}
   - 手机号：${{random_phone()}}
   - 随机文本：${{random_text(10)}}
   - 唯一标识：${{uuid()}}
   - 固定值直接写字符串
4. 必须包含验证步骤（assert），确认操作结果正确
5. 合理添加等待步骤（wait），确保元素加载完成
6. description 用中文简短描述每步操作意图

--------------------------------
【支持的 action type】
--------------------------------

- tap: 点击元素（需 selector）
- type: 输入文本（需 selector + text + clearFirst）
- scroll: 滚动（direction: up/down/left/right）
- wait: 等待（duration 毫秒数，可选 selector + condition）
- assert: 断言（condition: exists/not_exists/visible/text_equals/text_contains/enabled，可选 expected）
- screenshot: 截图
- back: 返回
- swipe: 滑动（direction + distance 0-1）

--------------------------------
【输出格式（严格 JSON，不要输出额外文字）】
--------------------------------

```json
{{
  "test_name": "测试用例名称",
  "description": "测试描述",
  "steps": [
    {{
      "type": "tap",
      "selector": {{ "strategy": "id", "value": "com.example:id/btn_login" }},
      "description": "点击登录按钮"
    }},
    {{
      "type": "type",
      "selector": {{ "strategy": "id", "value": "com.example:id/input_username" }},
      "text": "${{random_email()}}",
      "clearFirst": true,
      "description": "输入随机邮箱地址"
    }},
    {{
      "type": "wait",
      "duration": 2000,
      "description": "等待页面加载"
    }},
    {{
      "type": "assert",
      "condition": "visible",
      "selector": {{ "strategy": "id", "value": "com.example:id/welcome_text" }},
      "description": "验证欢迎文字显示"
    }}
  ],
  "confidence": 0.85,
  "notes": "补充说明或建议（如需要额外验证的场景）"
}}
```

只允许输出 JSON，不得输出额外解释文字。"""

COMPARE_PROMPT = """请对比两张移动端 App 截图（第一张为基线版本，第二张为当前版本），用中文输出差异分析：

对比维度：
1. 布局变化（元素位置移动、新增/删除区域）
2. 文案变化（文字修改、新增/删除文案）
3. 颜色/样式变化
4. 元素增删（新增按钮、移除图标等）
5. 功能变化推断

严格以 JSON 输出：
```json
{
  "differences": [
    {
      "category": "layout_change|text_change|color_change|element_added|element_removed|other",
      "description": "描述",
      "importance": "minor|moderate|significant",
      "is_regression": false
    }
  ],
  "overall_similarity": 90,
  "risk_level": "low|medium|high",
  "summary": "一句话总结"
}
```
overall_similarity 为 0-100 的整数，100 表示完全相同。"""

TEST_SUGGESTION_PROMPT = """请根据这张移动端 App 截图，建议下一步测试动作（用中文描述）：

分析维度：
1. 当前页面所有可交互元素
2. 从测试角度，合理的下一步操作
3. 建议的断言检查点
4. 边界条件和异常场景

严格以 JSON 输出：
```json
{
  "suggested_actions": [
    {"action": "click|input|swipe|...", "target": "目标元素", "description": "操作说明"}
  ],
  "suggested_assertions": [
    {"type": "element_exists|text_contains|state_check", "target": "目标", "expected": "期望值"}
  ],
  "navigation_options": [
    {"direction": "跳转目标", "trigger": "触发方式"}
  ]
}
```"""


class LLMClient:
    """LLM client for AI-powered screenshot and test analysis."""

    def __init__(self):
        client_kwargs: dict[str, Any] = {}
        if settings.llm_base_url:
            client_kwargs["base_url"] = settings.llm_base_url

        self._client = AsyncOpenAI(api_key=settings.llm_api_key, **client_kwargs)
        self.model = settings.llm_chat_model
        self.vl_model = settings.llm_vl_chat_model or settings.llm_chat_model
        self.embedding_model = settings.llm_embedding_model
        self.embedding_dimensions = settings.llm_embedding_dimensions
        self.timeout = settings.ai_analysis_timeout

    # ------------------------------------------------------------------
    # Embedding (text-only, uses self.model)
    # ------------------------------------------------------------------

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> list[float]:
        """Create an embedding vector for text."""
        kwargs: dict[str, Any] = {
            "model": model or self.embedding_model,
            "input": text,
            "timeout": self.timeout,
        }

        if self.embedding_dimensions:
            kwargs["dimensions"] = self.embedding_dimensions

        try:
            response = await self._client.embeddings.create(**kwargs)
        except TypeError:
            kwargs.pop("dimensions", None)
            response = await self._client.embeddings.create(**kwargs)

        return list(response.data[0].embedding)

    # ------------------------------------------------------------------
    # Internal: multimodal chat.completions call
    # ------------------------------------------------------------------

    @staticmethod
    def _png_data_url(png_bytes: bytes) -> str:
        image_base64 = base64.b64encode(png_bytes).decode("utf-8")
        return f"data:image/png;base64,{image_base64}"

    async def _chat_multimodal(
        self,
        images: list[bytes],
        prompt_text: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a multimodal request using chat.completions API.

        Always uses the **vision-language model** (self.vl_model) so that
        image inputs are properly processed.
        """
        messages: list[dict[str, Any]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user content with images + text
        content: list[dict[str, Any]] = []
        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": self._png_data_url(img)},
            })
        content.append({"type": "text", "text": prompt_text})

        messages.append({"role": "user", "content": content})

        response = await self._client.chat.completions.create(
            model=self.vl_model,
            messages=messages,
            timeout=self.timeout,
        )
        message = response.choices[0].message
        return message.content or json.dumps(response.model_dump(), ensure_ascii=False)

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON from model output, handling markdown fences."""
        cleaned = text.strip()
        # Strip markdown code fences
        if cleaned.startswith("```"):
            first_nl = cleaned.find("\n")
            if first_nl != -1:
                cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].rstrip()
        # Try JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to extract JSON block from mixed output
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start: end + 1])
                except json.JSONDecodeError:
                    pass
            return {"raw_response": text}

    # ------------------------------------------------------------------
    # Public API: screenshot analysis
    # ------------------------------------------------------------------

    async def analyze_screenshot(
        self,
        screenshot_bytes: bytes,
        analysis_type: str = "ui_state",
        additional_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze a screenshot using the vision-language model."""
        prompt_text = PROMPTS.get(analysis_type, PROMPTS["ui_state"])
        if additional_context:
            prompt_text += f"\n\n补充上下文（中文）：{additional_context}"

        start_time = time.time()
        try:
            output_text = await self._chat_multimodal(
                images=[screenshot_bytes],
                prompt_text=prompt_text,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "analysis_type": analysis_type,
                "result": self._parse_json_response(output_text),
                "model": self.vl_model,
                "latency_ms": latency_ms,
                "confidence": 0.85,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "analysis_type": analysis_type,
                "error": str(e),
                "model": self.vl_model,
                "latency_ms": latency_ms,
                "confidence": 0.0,
            }

    # ------------------------------------------------------------------
    # Public API: page structure analysis (screenshot + XML)
    # ------------------------------------------------------------------

    async def analyze_page_structure(
        self,
        screenshot_bytes: bytes,
        page_source_xml: str,
    ) -> dict[str, Any]:
        """Analyze a mobile page using both screenshot and XML page source."""
        start_time = time.time()

        # Truncate very large XML to avoid exceeding token limits
        max_xml_chars = 60000
        xml_truncated = False
        xml_content = page_source_xml
        if len(xml_content) > max_xml_chars:
            xml_content = xml_content[:max_xml_chars]
            xml_truncated = True

        truncation_note = ""
        if xml_truncated:
            truncation_note = "\n（注意：XML 内容因长度过大已截断，请基于已提供的部分进行分析）\n"

        prompt_text = PAGE_STRUCTURE_PROMPT.format(
            xml_content=xml_content,
            truncation_note=truncation_note,
        )

        try:
            output_text = await self._chat_multimodal(
                images=[screenshot_bytes],
                prompt_text=prompt_text,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "analysis_type": "page_structure",
                "result": self._parse_json_response(output_text),
                "model": self.vl_model,
                "latency_ms": latency_ms,
                "confidence": 0.90,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "analysis_type": "page_structure",
                "error": str(e),
                "model": self.vl_model,
                "latency_ms": latency_ms,
                "confidence": 0.0,
            }

    # ------------------------------------------------------------------
    # Public API: screenshot comparison
    # ------------------------------------------------------------------

    async def compare_screenshots(
        self,
        baseline_bytes: bytes,
        target_bytes: bytes,
    ) -> dict[str, Any]:
        """Compare two screenshots for visual differences."""
        start_time = time.time()

        try:
            output_text = await self._chat_multimodal(
                images=[baseline_bytes, target_bytes],
                prompt_text=COMPARE_PROMPT,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "result": self._parse_json_response(output_text),
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

    # ------------------------------------------------------------------
    # Public API: test step suggestion
    # ------------------------------------------------------------------

    async def generate_test_suggestion(
        self,
        screenshot_bytes: bytes,
        current_test_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate test step suggestions based on current screen."""
        prompt_text = TEST_SUGGESTION_PROMPT
        if current_test_context:
            prompt_text += f"\n\n当前测试上下文（中文）：{current_test_context}"

        start_time = time.time()

        try:
            output_text = await self._chat_multimodal(
                images=[screenshot_bytes],
                prompt_text=prompt_text,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "result": self._parse_json_response(output_text),
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

    # ------------------------------------------------------------------
    # Public API: generate test steps from screenshot + XML
    # ------------------------------------------------------------------

    async def generate_test_steps(
        self,
        screenshot_bytes: bytes,
        page_source_xml: str,
        platform: str = "android",
        test_scenario: str | None = None,
    ) -> dict[str, Any]:
        """Generate executable test case steps from a page screenshot and XML."""
        start_time = time.time()

        # Truncate large XML
        max_xml_chars = 60000
        xml_content = page_source_xml
        truncation_note = ""
        if len(xml_content) > max_xml_chars:
            xml_content = xml_content[:max_xml_chars]
            truncation_note = "\n（注意：XML 内容因长度过大已截断，请基于已提供的部分进行分析）\n"

        scenario_context = f"测试场景：{test_scenario}" if test_scenario else "测试场景：自动识别页面功能并生成核心测试流程"

        prompt_text = GENERATE_TEST_STEPS_PROMPT.format(
            xml_content=xml_content,
            truncation_note=truncation_note,
            platform=platform,
            scenario_context=scenario_context,
        )

        try:
            output_text = await self._chat_multimodal(
                images=[screenshot_bytes],
                prompt_text=prompt_text,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            latency_ms = int((time.time() - start_time) * 1000)

            result = self._parse_json_response(output_text)

            # Ensure steps is a list
            if isinstance(result, dict) and "steps" in result:
                steps = result["steps"]
                if not isinstance(steps, list):
                    result["steps"] = []
            else:
                result = {"test_name": "AI Generated Test", "steps": [], "confidence": 0.0, "notes": "No steps generated"}

            return {
                "success": True,
                "result": result,
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.vl_model,
                "latency_ms": latency_ms,
            }

    # ------------------------------------------------------------------
    # Public API: text-only chat (for run summary, no images)
    # ------------------------------------------------------------------

    async def chat_text(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Send a text-only chat request using the regular chat model."""
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            timeout=self.timeout,
        )
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
