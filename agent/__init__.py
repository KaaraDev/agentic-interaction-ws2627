"""Calendar agent: a model that answers questions by calling tools in a loop.

Module overview (see README):
    __main__   command line entry point: run, print, log the end, exit code
    config     settings from the environment / .env
    agent      the agent loop (one model call per step)
    llm        HTTP client for the OpenAI-compatible endpoint, retries
    tools/     tool registry and the calendar tool
    policies   what to do when the token limit is reached (ask the user / wait)
    guards     checks on the model's answer before it is accepted
    prompts    all texts sent to the model
    log        JSONL run log
    errors     exceptions and exit codes
"""
