import multiprocessing.managers
import logging
import click

log = logging.getLogger('werkzeug')


class ListHandler(logging.Handler):
    def __init__(self, list_obj: list | multiprocessing.managers.ListProxy, maxsize, change_flag, tui_event):
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


# Disable "click text-line interface"
def secho(text, file=None, nl=None, err=None, color=None, **styles):
    pass


def echo(text, file=None, nl=None, err=None, color=None, **styles):
    pass


click.echo = echo
click.secho = secho


def rest_api():
    # list_handler = ListHandler()
    # loguru_handler = LoguruHandler()
    # log.addHandler(list_handler)
    # log.addHandler(loguru_handler)
    ...

