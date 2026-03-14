## Overview

Flux provides an RPC server for communicating with LLM backends. Specifically, it takes care of the following operations:

- Providing a unified interface for LLM messages and tool calls.
- Using this unified interface to communicate with a disparate set of LLM providers. Under the hood, this is handled by [pi-ai](https://github.com/badlogic/pi-mono/tree/main/packages/ai), which in turn, eventually delegates to vendor-specific libraries after translation/normalization.
