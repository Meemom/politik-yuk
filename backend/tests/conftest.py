import os


def pytest_configure() -> None:
    os.environ["ENVIRONMENT"] = "test"
    os.environ["MODEL_PROVIDER_BACKEND"] = "fake"
    os.environ["EXTERNAL_SEARCH_PROVIDER"] = "disabled"
    os.environ["GRAPH_CHECKPOINT_BACKEND"] = "memory"
    os.environ["ALLOW_INMEMORY_REDIS"] = "true"
    os.environ["COHERE_API_KEY"] = ""
    os.environ["TAVILY_API_KEY"] = ""
    os.environ["BRAVE_SEARCH_API_KEY"] = ""
