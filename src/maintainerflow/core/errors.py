class MaintainerFlowError(Exception):
    """Base domain error."""


class InvalidSignatureError(MaintainerFlowError):
    """Webhook signature is missing or invalid."""


class InvalidEventPayloadError(MaintainerFlowError):
    """Webhook JSON does not match the supported schema."""


class UnsupportedEventError(MaintainerFlowError):
    """Webhook event or action is intentionally ignored."""


class DuplicateDeliveryError(MaintainerFlowError):
    """Delivery has already been recorded."""


class TransientDependencyError(MaintainerFlowError):
    """A dependency failed and the operation may be retried."""


class PermanentDependencyError(MaintainerFlowError):
    """A dependency rejected an operation that retrying cannot repair."""
