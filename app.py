import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Notification:
    def __init__(self, message, category):
        self.message = message
        self.category = category
        self.timestamp = self.get_timestamp()

    def get_timestamp(self):
        return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    def log_notification(self):
        logging.info(f'[{self.timestamp}] [{self.category}] {self.message}') 

# Example usage
if __name__ == '__main__':
    notification = Notification('New message received!', 'INFO')
    notification.log_notification()
    time.sleep(1)  # Simulate waiting for new notification
    notification = Notification('Another message received!', 'WARNING')
    notification.log_notification()