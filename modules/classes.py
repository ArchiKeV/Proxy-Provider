import multiprocessing
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


class ListHandler(logging.Handler):
    def __init__(
            self, list_obj: list | multiprocessing.managers.ListProxy, maxsize, change_flag, tui_event,
            log: logging.Logger
    ):
        if not isinstance(list_obj, list | multiprocessing.managers.ListProxy):
            log.error("ListHandler init error: Accepts only a list object")
            raise TypeError("Accepts only a list object")
        logging.Handler.__init__(self)
        self.log_queue = list_obj
        self.maxsize = maxsize
        self.change_flag = change_flag
        self.tui_event = tui_event

    def emit(self, record):
        self.log_queue.append(self.format(record))
        self.shrink()
        self.change_flag.value = True
        self.tui_event.set()

    def shrink(self):
        if self.maxsize is None or self.maxsize >= len(self.log_queue):
            return
        else:
            while self.maxsize < len(self.log_queue):
                self.log_queue.pop(0)
