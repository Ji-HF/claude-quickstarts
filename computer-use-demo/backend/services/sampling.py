"""Adapted sampling loop that streams events for the FastAPI backend."""

import asyncio
import json
import logging
import os
import platform
import traceback
from datetime import datetime
from typing import Any, cast

from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
)
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from computer_use_demo.tools import TOOL_GROUPS_BY_VERSION, ToolCollection, ToolResult, ToolVersion

logger = logging.getLogger(__name__)


def _convert_messages_for_openai(messages: list[BetaMessageParam], system_text: str) -> list[dict[str, Any]]:
    """Convert Anthropic-format messages to OpenAI-compatible format."""
    openai_messages: list[dict[str, Any]] = [{"role": "system", "content": system_text}]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts) if text_parts else ""
        openai_messages.append({"role": role, "content": content})
    return openai_messages


async def run_deepseek_loop(
    *,
    model: str,
    api_key: str,
    base_url: str,
    messages: list[BetaMessageParam],
    system_prompt_suffix: str,
    broadcast: Any,
    cancel_event: asyncio.Event,
) -> list[BetaMessageParam]:
    """Run a simple chat loop using DeepSeek's OpenAI-compatible API.

    DeepSeek does not support Computer Use tools, so this is a basic
    chat completion without tool execution.
    """
    from openai import AsyncOpenAI

    effective_api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    effective_base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    effective_model = model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    if not effective_api_key:
        await broadcast("error", {"message": "No DeepSeek API key provided. Set DEEPSEEK_API_KEY."})
        return messages

    system_text = SYSTEM_PROMPT
    if system_prompt_suffix:
        system_text = f"{SYSTEM_PROMPT} {system_prompt_suffix}"

    openai_messages = _convert_messages_for_openai(messages, system_text)

    client = AsyncOpenAI(api_key=effective_api_key, base_url=effective_base_url)

    await broadcast("status", {"message": "Calling DeepSeek API...", "phase": "api_call"})

    if cancel_event.is_set():
        await broadcast("cancelled", {"message": "Session cancelled by user"})
        return messages

    try:
        stream = await client.chat.completions.create(
            model=effective_model,
            messages=openai_messages,
            stream=True,
            max_tokens=8192,
        )

        full_text = ""
        async for chunk in stream:
            if cancel_event.is_set():
                await broadcast("cancelled", {"message": "Session cancelled by user"})
                await stream.close()
                return messages

            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                full_text += delta.content
                await broadcast("text_delta", {"text": delta.content})

        # Build assistant message in Anthropic format for DB compatibility
        assistant_content: list[BetaContentBlockParam] = [
            BetaTextBlockParam(type="text", text=full_text)
        ]
        messages.append({"role": "assistant", "content": assistant_content})

        await broadcast("done", {"message": "Turn complete"})

    except Exception as e:
        logger.exception("DeepSeek API error")
        await broadcast("error", {"message": str(e), "type": "deepseek_error"})

    return messages

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* To open firefox, please just click on the firefox icon.  Note, firefox-esr is what is installed on your system.
* Using bash tool you can start GUI applications, but you need to set export DISPLAY=:1 and use a subshell. For example "(DISPLAY=:1 xterm &)". GUI apps run with bash tool will appear within your desktop environment, but they may take some time to appear. Take a screenshot to confirm it did.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_based_edit_tool or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* When using Firefox, if a startup wizard appears, IGNORE IT.  Do not even click "skip this step".  Instead, click on the address bar where it says "Search or enter address", and enter the appropriate search term or URL there.
* If the item you are looking at is a pdf, if after taking a single screenshot of the pdf it seems that you want to read the entire document instead of trying to continue to read the pdf from your screenshots + navigation, determine the URL, use curl to download the pdf, install and use pdftotext to convert it to a text file, and then read that text file directly with your str_replace_based_edit_tool.
</IMPORTANT>"""


async def run_sampling_loop(
    *,
    session_id: str,
    model: str,
    provider: str,
    api_key: str,
    messages: list[BetaMessageParam],
    tool_version: ToolVersion,
    max_tokens: int = 16384,
    only_n_most_recent_images: int | None = None,
    system_prompt_suffix: str = "",
    thinking_mode: str = "adaptive",
    thinking_effort: str = "medium",
    thinking_budget: int | None = None,
    token_efficient_tools_beta: bool = False,
    broadcast: Any,  # callable: async (event_type, data) -> None
    cancel_event: asyncio.Event,
) -> list[BetaMessageParam]:
    """Run the agent sampling loop, streaming all events via broadcast callback.

    Returns the updated message list.
    """
    # Validate API key for Anthropic provider
    effective_api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    # Dispatch to DeepSeek if configured
    if provider == "deepseek":
        deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        return await run_deepseek_loop(
            model=deepseek_model,
            api_key=api_key,
            base_url=deepseek_base_url,
            messages=messages,
            system_prompt_suffix=system_prompt_suffix,
            broadcast=broadcast,
            cancel_event=cancel_event,
        )

    if provider == "anthropic" and not effective_api_key:
        await broadcast("error", {"message": "No API key provided. Set ANTHROPIC_API_KEY or provide it in session config."})
        return messages

    tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
    tool_collection = ToolCollection(*(ToolCls() for ToolCls in tool_group.tools))
    system = BetaTextBlockParam(
        type="text",
        text=f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )

    while True:
        if cancel_event.is_set():
            await broadcast("cancelled", {"message": "Session cancelled by user"})
            break

        enable_prompt_caching = False
        betas: list[str] = [tool_group.beta_flag] if tool_group.beta_flag else []
        if token_efficient_tools_beta:
            betas.append("token-efficient-tools-2025-02-19")
        image_truncation_threshold = only_n_most_recent_images or 0

        if provider == "anthropic":
            client: Any = Anthropic(api_key=effective_api_key, max_retries=4)
            enable_prompt_caching = True
        elif provider == "vertex":
            client = AnthropicVertex()
        elif provider == "bedrock":
            client = AnthropicBedrock()
        else:
            client = Anthropic(api_key=effective_api_key, max_retries=4)

        if enable_prompt_caching:
            betas.append(PROMPT_CACHING_BETA_FLAG)
            _inject_prompt_caching(messages)
            only_n_most_recent_images = 0
            system["cache_control"] = {"type": "ephemeral"}  # type: ignore[typeddict-item]

        if only_n_most_recent_images:
            _maybe_filter_to_n_most_recent_images(
                messages, only_n_most_recent_images, image_truncation_threshold
            )

        extra_body: dict[str, Any] = {}
        if thinking_mode == "adaptive":
            extra_body = {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": thinking_effort},
            }
        elif thinking_mode == "extended" and thinking_budget:
            extra_body = {
                "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
            }

        # Stream status
        await broadcast("status", {"message": "Calling Claude API...", "phase": "api_call"})

        try:
            raw_response = client.beta.messages.with_raw_response.create(
                max_tokens=max_tokens,
                messages=messages,
                model=model,
                system=[system],
                tools=tool_collection.to_params(),
                betas=betas,
                extra_body=extra_body,
            )
        except (APIStatusError, APIResponseValidationError) as e:
            error_detail = {
                "status_code": getattr(e, "status_code", None),
                "message": str(e),
            }
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail["body"] = json.loads(e.response.text)
                except Exception:
                    error_detail["body"] = str(getattr(e.response, "text", ""))
            await broadcast("error", error_detail)
            break
        except APIError as e:
            await broadcast("error", {"message": str(e), "type": "api_error"})
            break
        except Exception as e:
            await broadcast("error", {"message": str(e), "type": "unknown", "traceback": traceback.format_exc()})
            break

        response: BetaMessage = raw_response.parse()
        response_params = _response_to_params(response)

        messages.append({"role": "assistant", "content": response_params})

        tool_result_content: list[BetaToolResultBlockParam] = []
        for content_block in response_params:
            if isinstance(content_block, dict):
                if content_block.get("type") == "text":
                    await broadcast("text_delta", {"text": content_block["text"]})
                elif content_block.get("type") == "thinking":
                    await broadcast("thinking", {"thinking": content_block.get("thinking", "")})
                elif content_block.get("type") == "tool_use":
                    await broadcast("tool_use", {
                        "id": content_block["id"],
                        "name": content_block["name"],
                        "input": content_block["input"],
                    })

            # Execute tools
            if isinstance(content_block, dict) and content_block.get("type") == "tool_use":
                tool_use_block = cast(BetaToolUseBlockParam, content_block)
                try:
                    result = await tool_collection.run(
                        name=tool_use_block["name"],
                        tool_input=cast(dict[str, Any], tool_use_block.get("input", {})),
                    )
                except Exception as e:
                    result = ToolResult(error=str(e))

                tool_result_content.append(
                    _make_api_tool_result(result, tool_use_block["id"])
                )

                # Broadcast tool result
                tool_result_data: dict[str, Any] = {
                    "tool_use_id": tool_use_block["id"],
                    "output": result.output,
                    "error": result.error,
                }
                if result.base64_image:
                    tool_result_data["base64_image"] = result.base64_image
                await broadcast("tool_result", tool_result_data)

        if not tool_result_content:
            await broadcast("done", {"message": "Turn complete – no more tool calls"})
            break

        messages.append({"content": tool_result_content, "role": "user"})

    return messages


def _response_to_params(response: BetaMessage) -> list[BetaContentBlockParam]:
    res: list[BetaContentBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            if block.text:
                res.append(BetaTextBlockParam(type="text", text=block.text))
            elif getattr(block, "type", None) == "thinking":
                thinking_block: dict[str, Any] = {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", None),
                }
                if hasattr(block, "signature"):
                    thinking_block["signature"] = getattr(block, "signature", None)
                res.append(cast(BetaContentBlockParam, thinking_block))
        else:
            res.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return res


def _inject_prompt_caching(messages: list[BetaMessageParam]) -> None:
    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(content := message["content"], list):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                content[-1]["cache_control"] = BetaCacheControlEphemeralParam(  # type: ignore[typeddict-item]
                    {"type": "ephemeral"}
                )
            else:
                if isinstance(content[-1], dict) and "cache_control" in content[-1]:
                    del content[-1]["cache_control"]  # type: ignore[typeddict-item]
                break


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int,
) -> None:
    if images_to_keep is None:
        return

    tool_result_blocks = cast(
        list[BetaToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content: list[Any] = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _make_api_tool_result(result: ToolResult, tool_use_id: str) -> BetaToolResultBlockParam:
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append({
                "type": "text",
                "text": _maybe_prepend_system_tool_result(result, result.output),
            })
        if result.base64_image:
            tool_result_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": result.base64_image,
                },
            })
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str) -> str:
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text
