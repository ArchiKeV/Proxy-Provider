import logging
import loguru


class LoguruHandler(logging.Handler):
    def __init__(self, loguru_log: loguru.logger):
        logging.Handler.__init__(self)
        self.loguru_logger = loguru_log

    def emit(self, record):
        raw_level_no = record.levelno
        level_name = {
            50: 'critical', 40: 'error', 30: 'warning',
            20: 'info', 10: 'debug', 0: 'trace'
        }
        if raw_level_no < 10:
            level_no = 0
        elif 10 <= raw_level_no < 20:
            level_no = 10
        elif 20 <= raw_level_no < 30:
            level_no = 20
        elif 30 <= raw_level_no < 40:
            level_no = 30
        elif 40 <= raw_level_no < 50:
            level_no = 40
        else:
            level_no = 50

        getattr(self.loguru_logger, level_name[level_no])(self.format(record))
