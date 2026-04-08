import asyncio

from agentron import make_agent


def get_current_city() -> str:
    """
    Returns the name of the user's current city.
    """
    return 'San Francisco'


def get_calvinball_team_name(city: str) -> str:
    """
    Returns the name of the local Calvinball team in the specified city.
    Args:
        city: The name of the city to get the team name for.
    """
    return f'{city} Sprockets'


async def main():
    agent = make_agent(
        system_prompt="You are a helpful assistant. Use the available tools to answer the user's question.",
        tools=[
            get_current_city,
            get_calvinball_team_name,
        ],
        model='openrouter:openrouter/free',
        terminal=True,
    )
    response = await agent.ask('What is the name of the local Calvinball team in my city?')
    print('Agent response:', response)


if __name__ == '__main__':
    asyncio.run(main())
