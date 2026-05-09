class NistulaBaseError(Exception):
    pass

class PropertyNotFoundError(NistulaBaseError):
    pass

class MessageProcessingError(NistulaBaseError):
    pass

class AIAuthenticationError(NistulaBaseError):
    pass

class AIRateLimitError(NistulaBaseError):
    pass

class AIServiceError(NistulaBaseError):
    pass

class AITimeoutError(NistulaBaseError):
    pass