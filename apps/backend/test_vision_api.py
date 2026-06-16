"""Test script for Alibaba Cloud Qwen/DashScope vision model connectivity.

Run from the backend directory:
    python test_vision_api.py

Requires: QWEN_API_KEY set in .env
"""
from __future__ import annotations

import asyncio
import base64
import io
import sys
import time


def _make_tiny_png() -> bytes:
    """Generate a tiny 100x100 red PNG in memory using PIL.

    Falls back to a minimal hardcoded PNG if PIL is not installed.
    """
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        # Draw a simple white rectangle to simulate a UI element
        for y in range(30, 70):
            for x in range(20, 80):
                img.putpixel((x, y), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        # Minimal 1x1 red PNG (67 bytes)
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )


async def test_text_model():
    """Test 1: Basic text-only chat completion."""
    from app.core.config import settings

    print(f"\n{'='*60}")
    print("TEST 1: Text-only chat model")
    print(f"  Model:    {settings.llm_chat_model}")
    print(f"  Provider: {settings.llm_provider}")
    print(f"  Base URL: {settings.llm_base_url}")
    print(f"  API Key:  {'***' + (settings.llm_api_key or '')[-6:] if settings.llm_api_key else 'NOT SET'}")
    print(f"{'='*60}")

    if not settings.llm_api_key:
        print("  [FAIL] API key not configured!")
        return False

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    start = time.time()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_chat_model,
            messages=[
                {"role": "system", "content": "用中文回答，只回复一个词。"},
                {"role": "user", "content": "你好，请说一个字"},
            ],
            timeout=30,
        )
        latency = int((time.time() - start) * 1000)
        content = response.choices[0].message.content
        print(f"  Response: {content}")
        print(f"  Latency:  {latency}ms")
        print(f"  [PASS] Text model works!")
        return True
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        print(f"  [FAIL] {type(e).__name__}: {e}  ({latency}ms)")
        return False


async def test_vision_model():
    """Test 2: Vision-language model with a tiny image."""
    from app.core.config import settings

    vl_model = settings.llm_vl_chat_model
    print(f"\n{'='*60}")
    print("TEST 2: Vision-language model (image analysis)")
    print(f"  Model:    {vl_model}")
    print(f"  Base URL: {settings.llm_base_url}")
    print(f"{'='*60}")

    if not settings.llm_api_key:
        print("  [FAIL] API key not configured!")
        return False

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    png_bytes = _make_tiny_png()
    data_url = f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"

    start = time.time()
    try:
        response = await client.chat.completions.create(
            model=vl_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是移动端UI分析专家，用中文简短回答。",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                        {
                            "type": "text",
                            "text": "请描述这张图片中你看到的内容（简短即可）",
                        },
                    ],
                },
            ],
            timeout=60,
        )
        latency = int((time.time() - start) * 1000)
        content = response.choices[0].message.content
        print(f"  Response: {content}")
        print(f"  Latency:  {latency}ms")
        print(f"  [PASS] Vision model works!")
        return True
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        print(f"  [FAIL] {type(e).__name__}: {e}  ({latency}ms)")
        return False


async def test_full_analysis():
    """Test 3: Full screenshot analysis with the LLMClient class."""
    from app.core.config import settings

    print(f"\n{'='*60}")
    print("TEST 3: Full analysis pipeline (LLMClient.analyze_screenshot)")
    print(f"  VL Model: {settings.llm_vl_chat_model}")
    print(f"{'='*60}")

    if not settings.llm_api_key:
        print("  [FAIL] API key not configured!")
        return False

    # Reset singleton so fresh config is loaded
    import app.integrations.llm.client as llm_mod
    llm_mod._llm_client = None
    from app.integrations.llm.client import get_llm_client

    client = get_llm_client()
    print(f"  client.model    = {client.model}")
    print(f"  client.vl_model = {client.vl_model}")

    png_bytes = _make_tiny_png()

    # Test anomaly analysis
    start = time.time()
    result = await client.analyze_screenshot(
        screenshot_bytes=png_bytes,
        analysis_type="anomaly",
    )
    latency = int((time.time() - start) * 1000)

    print(f"  Success:     {result.get('success')}")
    print(f"  Latency:     {result.get('latency_ms')}ms (total wall: {latency}ms)")
    print(f"  Model:       {result.get('model')}")

    if result.get("success"):
        import json
        result_json = result.get("result", {})
        print(f"  Has anomaly: {result_json.get('has_anomaly', 'N/A')}")
        print(f"  Summary:     {result_json.get('summary', 'N/A')}")
        print(f"  Raw result:  {json.dumps(result_json, ensure_ascii=False)[:200]}...")
        print(f"  [PASS] Full analysis pipeline works!")
        return True
    else:
        print(f"  Error:       {result.get('error')}")
        print(f"  [FAIL]")
        return False


async def test_page_structure():
    """Test 4: Page structure analysis with XML."""
    from app.core.config import settings

    print(f"\n{'='*60}")
    print("TEST 4: Page structure analysis (screenshot + XML)")
    print(f"  VL Model: {settings.llm_vl_chat_model}")
    print(f"{'='*60}")

    if not settings.llm_api_key:
        print("  [FAIL] API key not configured!")
        return False

    import app.integrations.llm.client as llm_mod
    llm_mod._llm_client = None
    from app.integrations.llm.client import get_llm_client

    client = get_llm_client()
    png_bytes = _make_tiny_png()

    fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example.app" content-desc="" checkable="false"
        checked="false" clickable="false" enabled="true"
        focusable="false" focused="false" scrollable="false"
        long-clickable="false" password="false" selected="false"
        bounds="[0,0][1080,2400]">
    <node index="0" text="登录" resource-id="com.example.app:id/title"
          class="android.widget.TextView" bounds="[432,200][648,280]"
          clickable="false" />
    <node index="1" text="" resource-id="com.example.app:id/username_input"
          class="android.widget.EditText" bounds="[108,400][972,500]"
          clickable="true" />
    <node index="2" text="" resource-id="com.example.app:id/password_input"
          class="android.widget.EditText" bounds="[108,550][972,650]"
          clickable="true" password="true" />
    <node index="3" text="登录" resource-id="com.example.app:id/login_btn"
          class="android.widget.Button" bounds="[108,750][972,850]"
          clickable="true" />
  </node>
</hierarchy>"""

    start = time.time()
    result = await client.analyze_page_structure(png_bytes, fake_xml)
    latency = int((time.time() - start) * 1000)

    print(f"  Success:  {result.get('success')}")
    print(f"  Latency:  {result.get('latency_ms')}ms (total wall: {latency}ms)")

    if result.get("success"):
        import json
        result_json = result.get("result", {})
        print(f"  Page type: {result_json.get('page_type', 'N/A')}")
        print(f"  Scores:    {json.dumps(result_json.get('scores', {}), ensure_ascii=False)}")
        print(f"  Risk:      {result_json.get('risk_level', 'N/A')}")
        elements = result_json.get("interactive_elements", [])
        print(f"  Elements:  {len(elements)} found")
        for el in elements[:3]:
            print(f"    - {el.get('element_type', '?')}: {el.get('display_text', '?')}")
        print(f"  [PASS] Page structure analysis works!")
        return True
    else:
        print(f"  Error:    {result.get('error')}")
        print(f"  [FAIL]")
        return False


async def main():
    print("\n" + "=" * 60)
    print("  NanoTest - Alibaba Cloud Vision Model API Test")
    print("=" * 60)

    results = {}

    results["text_model"] = await test_text_model()
    results["vision_model"] = await test_vision_model()
    results["full_analysis"] = await test_full_analysis()
    results["page_structure"] = await test_page_structure()

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total_pass = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  {total_pass}/{total} tests passed")

    if total_pass < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
