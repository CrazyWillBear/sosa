from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from sosa.Sosa import Sosa
from cli import display


async def run(agent: Sosa) -> None:
    messages = []

    while True:
        try:
            user_input = display.user_prompt()
        except (EOFError, KeyboardInterrupt):
            display.console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            display.console.print("\n[dim]Goodbye.[/dim]")
            break

        snapshot = len(messages)
        messages.append(HumanMessage(content=user_input))
        display.console.print()

        response_text = []

        try:
            async for msg in agent.run(messages):
                messages.append(msg)

                if isinstance(msg, AIMessage):
                    if msg.content:
                        response_text.append(msg.content)
                    for tc in msg.tool_calls:
                        display.tool_call(tc["name"], tc["args"])


        except KeyboardInterrupt:
            display.console.print("\n[dim]Interrupted.[/dim]\n")
            messages = messages[:snapshot]
            continue

        if response_text:
            display.agent_response(agent.name, "\n\n".join(response_text))
