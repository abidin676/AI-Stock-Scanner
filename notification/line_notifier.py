from notification.notifier import BaseNotifier


class LineNotifier(BaseNotifier):

    def send(self, message: str):
        raise NotImplementedError("LINE notifier is not configured.")
