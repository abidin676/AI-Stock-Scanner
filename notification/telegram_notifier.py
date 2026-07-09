from notification.notifier import BaseNotifier


class TelegramNotifier(BaseNotifier):

    def send(self, message: str):
        raise NotImplementedError("Telegram notifier is not configured.")
