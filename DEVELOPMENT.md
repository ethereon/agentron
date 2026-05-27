# Development

## Components

- [agentron](agentron): The main Python library
- [flux](packages/flux): Node.js RPC server that provides a unified API for interacting with various LLM providers. Written in TypeScript. See the section on _Communication Backend_ for more details.
- [webui](packages/webui): Web-based agent activity viewer.
- [ein](packages/ein): Shared TypeScript utility library.
- [agentypes](packages/agentypes): Shared, mostly auto-generated types used across components. See the section on _Auto Type Generation_ for more details.

## Building

- Run `npm install` at the project root.
- Use `npm run build` to build all packages and generate the WebUI bundle.
- Use `npm run watch` during development.
    - The WebUI bundle will need to be manually generated using `npm run bundle`.

## Auto Type Generation

The [generate_agentypes.py](scripts/generate_agentypes.py) script automatically translates shared interfaces defined in Python (agent messages, models, ...) to TypeScript.

To re-generate the types, run:

```sh
python scripts/generate_agentypes.py
```

## Running Unit Tests

Python unit tests are placed under [tests](tests). Run them using:

```sh
pytest
```

## Building Wheels

The [dist_build.py](scripts/dist_build.py) script builds and bundles all packages/dependencies and generates a Python wheel file under `dist/`

```sh
python scripts/dist_build.py
```

This script is automatically invoked by the publishing workflow described below.

## Publishing New Releases

- Publishing to PyPI and creating a release on GitHub is automatically handled using GitHub Actions.

- Creating a `v<...>` tag triggers the [Publish](.github/workflows/publish.yml) workflow which builds a wheel (using the `dist_build.py` script), publishes to PyPI, and creates a new GitHub release.

- PyPI authentication is automatically handled via [Trusted Publishing / OpenID Connect](https://docs.pypi.org/trusted-publishers/)

## Communication Backend

There are currently multiple APIs across providers. For example, OpenAI has both its legacy API and the newer Responses API. Anthropic has its own API. Other providers may claim compatibility with existing APIs such as OpenAI's, but still differ in subtle ways.

Several libraries attempt to abstract over these differences and expose a unified interface. Agentron uses [pi-ai](https://github.com/badlogic/pi-mono/tree/main/packages/ai) for this purpose.

Agentron lazily spawns a lightweight, process-wide Node.js RPC helper ([`flux`](packages/flux)) to communicate with LLMs via the pi-ai translation layer, which eventually delegates to provider-specific JavaScript SDKs. IPC occurs over Unix domain sockets.

This process is automatically torn down when the parent Python process exits.

## Internal Tools

Certain parts of Agentron use internal tools during development that are not yet publicly available. These include:

- `valinor`: Used by the type generation script to code-gen interface validation functions
- `mayo`: Used for generating bundled CSS and TypeScript sources from the sass-like DSL used by the WebUI
