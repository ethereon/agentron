class ToolError(RuntimeError):
    """
    The ToolError class provides a way for tools to signal an error
    during execution while controlling precisely the text returned to the LLM.

    For instance, a tool raising a ValueError('This value is garbage') may result
    in a response like so:
        ValueError: This value is garbage

    However, if the tool raises ToolError('This value is garbage'), the response will be exactly:
        This value is garbage

    In both cases, the tool call will be marked as failed.
    """

    def __init__(self, message: str):
        super().__init__(message)

    @property
    def message(self) -> str:
        return self.args[0]
