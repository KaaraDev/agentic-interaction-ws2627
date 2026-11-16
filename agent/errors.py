"""Exceptions and exit codes."""

EXIT_OK = 0
EXIT_ERROR = 1    # error, including hitting the step limit
EXIT_PARTIAL = 2  # stopped at the token limit, request only partly processed


class RunAborted(Exception):
    """Ends the run. main() logs it as the 'error' event and exits with `exit_code`."""

    def __init__(self, message: str, exit_code: int = EXIT_ERROR):
        super().__init__(message)
        self.exit_code = exit_code


class ConfigError(RunAborted):
    """A setting is missing or invalid."""


class RateLimited(Exception):
    """The model endpoint answered HTTP 429; `wait_s` is how long until the limit resets."""

    def __init__(self, wait_s: float, detail: str):
        super().__init__(detail)
        self.wait_s = wait_s


class ModelError(Exception):
    """A model call failed.

    transient:    trying again may help (5xx, network, garbled response)
    parse_failed: the model produced output the endpoint could not parse (HTTP 400)
    """

    def __init__(self, message: str, transient: bool = False, parse_failed: bool = False):
        super().__init__(message)
        self.transient = transient
        self.parse_failed = parse_failed


class ToolError(Exception):
    """A tool failed. The message is passed to the model as the tool result; the run goes on."""
