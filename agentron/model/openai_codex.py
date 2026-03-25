from agentron.types.model import Model
from agentron.types.repo import ModelRepo, ModelRepoPriority

CODEX_BASE_URL = 'https://chatgpt.com/backend-api'


class OpenAICodexModelRepo(ModelRepo):
    def __init__(self, parent: ModelRepo):
        self.parent = parent

    def get_priority(self, provider: str) -> ModelRepoPriority:
        return ModelRepoPriority.EXCLUSIVE if provider == 'openai-codex' else ModelRepoPriority.DEFAULT

    def get_model(self, provider: str, model: str) -> Model:
        if provider != 'openai-codex':
            raise LookupError('Unsupported provider')

        m = self.parent.get_model(provider='openai', model=model)
        m['provider'] = 'openai-codex'
        m['api'] = 'openai-codex-responses'
        m['base_url'] = CODEX_BASE_URL
        m['auth_env_vars'] = []

        return m
