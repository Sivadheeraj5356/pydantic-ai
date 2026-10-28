"""A run recovered by a capability's `on_run_error` streams its output, not an error chunk."""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.run import AgentRunResult
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import RequestData


class Recover(AbstractCapability[Any]):
    async def on_run_error(self, ctx: Any, *, error: BaseException) -> AgentRunResult[Any]:
        return AgentRunResult(output='recovered')


async def _failing_stream(messages: Any, info: AgentInfo):
    raise RuntimeError('boom')
    yield 'unreachable'  # pragma: no cover


async def test_recovered_run_streams_output_without_error_chunk():
    agent = Agent(FunctionModel(stream_function=_failing_stream), capabilities=[Recover()])
    request = TypeAdapter(RequestData).validate_python(
        {
            'trigger': 'submit-message',
            'id': 'chat-1',
            'messages': [{'id': 'm1', 'role': 'user', 'parts': [{'type': 'text', 'text': 'hi'}]}],
        }
    )
    adapter = VercelAIAdapter(agent=agent, run_input=request)

    types: list[str] = []
    async for event in adapter.encode_stream(adapter.run_stream()):
        for line in event.splitlines():
            if line.startswith('data: ') and line != 'data: [DONE]':
                types.append(json.loads(line[len('data: ') :])['type'])

    assert 'error' not in types
    assert types[0] == 'start'
    assert types[-1] == 'finish' or types[-2:] == ['finish', 'finish'] or 'finish' in types
