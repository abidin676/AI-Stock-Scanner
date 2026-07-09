from notification.notifier import BaseNotifier


class ConsoleNotifier(BaseNotifier):

    def send(self, message: str):
        print(message)
