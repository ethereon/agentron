# Agentron

Agentron is a modular Python toolkit for building AI agents. Its features include:

- Support for most major providers (OpenAI, Anthropic, Google, OpenRouter, ...), including certain subscription plans like ChatGPT Plus/Pro
- Defining custom tools for agents using plain Python functions and types
- Session persistence
- A web-based agent activity viewer (with streaming event support)
- Automatic model metadata discovery via services like [models.dev](https://models.dev)
- A collection of built-in tools that you can mix and match

## Installation

```bash
pip install agentron
```

### Requirements

- Python 3.12 or newer
- Node.js 20.19 or newer

## Example

```python
import asyncio

from agentron import make_agent

# Tools are regular Python functions (may be async).
# Agentron parses and validates the type annotations and
# docstrings to generate LLM-compatible tool schemas.

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
        # The latest model details are auto-fetched.
        # The API key (if not explicitly passed in here) is automatically resolved
        # from environment vars or ~/.agentron/auth.json
        model='openai:gpt-5.4',
        # Display agent activity in the terminal
        terminal=True,
    )
    response = await agent.ask('What is the name of the local Calvinball team in my city?')
    print('Agent response:', response)


asyncio.run(main())
```

## Models

Models can be accessed in multiple ways:

- As `<provider>:<model name>` strings (for example, `openai:gpt-5.4`) when using convenience functions like `make_agent`
- Via the [`get_model`](agentron/model/repo.py) function
- By manually instantiating a [`Model`](https://github.com/ethereon/agentron/blob/main/agentron/types/model.py) instance, potentially via [`make_model`](https://github.com/ethereon/agentron/blob/main/agentron/model/utils.py)

By default, Agentron uses online model metadata providers to resolve a model's details, such as its endpoint and context window. These currently include:

- [Models.dev](https://models.dev/)
- [OpenRouter](https://openrouter.ai/)

## Authentication

You can provide authentication details in several ways:

- Pass an API key explicitly using the `api_key` argument to `make_agent` (generally not recommended)
- Set a provider-specific environment variable (for example, `ANTHROPIC_API_KEY`)
- Add credentials to `~/.agentron/auth.json`:

    ```json
    {
        "zai-coding-plan": "<api key goes here>",
        "openai": "<api key goes here>",
        "openai:gpt-5.4": "<model-scoped api key goes here>"
    }
    ```

For subscription plans like ChatGPT Pro/Plus, Agentron needs to acquire an OAuth token. Use the built-in interactive login utility:

```bash
agentron login
```

## Tools

### Defining Tools

Agentron supports regular Python functions, callables, and types for defining tools:

```python
def my_custom_tool(arg_1: str, arg_2: int = 42) -> str:
    """
    A description for my custom tool.

    Args:
        arg_1: This is a description of the first argument.
        arg_2: This is a description of the second argument.
               It may span multiple lines.
    """
    ...
```

As shown above, for a Python function to be used as a tool, it must:

- Specify type annotations for all arguments
- Use [Google-style](https://google.github.io/styleguide/pyguide.html#383-functions-and-methods) docstrings to provide a function description and descriptions for each argument under the `Args` section (validated at runtime by Agentron)

Agentron automatically parses the function above to generate an LLM-compatible tool schema like the following:

```json
{
    "name": "my_custom_tool",
    "description": "A description for my custom tool.",
    "parameters": {
        "type": "object",
        "properties": {
            "arg_1": {
                "type": "string",
                "description": "This is a description of the first argument."
            },
            "arg_2": {
                "type": "integer",
                "description": "This is a description for the second argument. It may span multiple lines."
            }
        },
        "required": ["arg_1"]
    }
}
```

The following are supported:

- Python primitive types (`int`, `float`, `str`, `bool`, `None`)
- Unions (for example, `str | None`)
- `list` (for example, `list[str]`) and `dict` (for example, `dict[str, int]`)
- [`TypedDict`](https://typing.python.org/en/latest/spec/typeddict.html)
- [`dataclass`](https://docs.python.org/3/library/dataclasses.html)
- Callable class instances
- [Partial functions](https://docs.python.org/3/library/functools.html#functools.partial)

### Built-in Tools

Agentron includes a collection of built-in tools under the `agentron.kit` submodule. These currently include:

- [Filesystem I/O](agentron/kit/io.py): `read_file`, `write_file`, `apply_patch`
- [Shell calls](agentron/kit/shell.py): `bash`, `git`, `grep`
- A stateful [Python REPL for agents](agentron/kit/repl.py)

The built-in `agentron code` command provides a minimal coding agent implementation built using these tools.

## Persistence

Specifying the `output` argument causes Agentron to persist session events (metadata, messages, ...) as JSONL files, written as events complete:

```python
agent = make_agent(
    # If this path points to an existing directory, session events will
    # automatically be written to a file under it named <session_id>.jsonl.
    # Otherwise, the path is treated as the target JSONL file.
    output="/path/to/output",
    ...
)
```

For more details, see [`serialization.py`](agentron/serialization.py).

## Web UI

Agentron includes a local web-based UI for observing agent activity and viewing past sessions.

To monitor a session and launch the web server:

```python
from agentron.web import serve

agent = make_agent(...)

# Launch the web server (opens a browser by default).
# Multiple agents may be specified.
with serve(agent):
    # Perform tasks with agent
    ...
```

To view previously saved sessions, use the `web` command:

```bash
agentron web <path to .jsonl or a directory containing one or more .jsonl files>
```

## Agent Events

The `Agent` instance exposes a set of _publishers_ that trigger whenever certain events occur:

- `on_new_message`: Published whenever a new message (user, assistant, ...) is added to the session
- `on_streaming_message`: Published as a new assistant response streams in
- `on_tool_call`: Published before executing a tool call (see also: tool manager)

These events are used by components like the Web UI and automatic persistence. You can observe them like this:

```python
from agentron.types.message import AgentMessage

def handle_new_message(msg: AgentMessage) -> None:
    ...

# Start receiving new message events
unsubscribe = agent.on_new_message.subscribe(handle_new_message)
...

# Stop receiving new message events
unsubscribe()
```

## Technical Notes

### Communication Backend

There are currently multiple APIs across providers. For example, OpenAI has both its legacy API and the newer Responses API. Anthropic has its own API. Other providers may claim compatibility with existing APIs such as OpenAI's, but still differ in subtle ways.

Several libraries attempt to abstract over these differences and expose a unified interface. Agentron uses [pi-ai](https://github.com/badlogic/pi-mono/tree/main/packages/ai) for this purpose.

Agentron lazily spawns a lightweight, process-wide Node.js RPC helper ([`flux`](packages/flux)) to communicate with LLMs via the pi-ai translation layer, which eventually delegates to provider-specific JavaScript SDKs. IPC occurs over Unix domain sockets.

This process is automatically torn down when the parent Python process exits.

## License

Provided under the MIT License.
