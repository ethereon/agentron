import asyncio

from agentron import make_agent, Agent


async def review_code(code: str) -> str:
    """
    Reviews the given code and returns feedback.

    Args:
        code: The code to be reviewed.
    """
    parent = Agent.get_active()
    subagent = make_agent(
        system_prompt='You are a code review assistant. Provide feedback on the following code.',
        # The model and API key are inherited from the parent agent here.
        # However, a separate model/api-key can also be specified if desired.
        #
        # If the parent agent has persistence enabled, the subagent's events are also
        # automatically persisted, scoped under the parent agent's session.
        parent=parent,
        terminal=True,
    )

    with subagent:
        response = await subagent.ask(prompt=code)

    return response or 'No feedback.'


async def main():
    agent = make_agent(
        system_prompt="You are a helpful assistant. Use the available tools to answer the user's question.",
        tools=[review_code],
        model='openrouter:openrouter/free',
        terminal=True,
        # Uncomment the line below to enable persistence for the main agent.
        # The subagent's events will also be persisted under the same session.
        # Use `agentron web ~/agentron_sessions` to view it in the WebUI.
        # output='~/agentron_sessions/',
    )
    response = await agent.ask('Review this code: average = lambda nums: sum(nums) / len(nums)')
    print('Main agent response:', response)


if __name__ == '__main__':
    asyncio.run(main())
