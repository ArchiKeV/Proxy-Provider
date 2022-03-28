from flask import Flask
from sqlalchemy.orm import sessionmaker
from loguru import logger
import logging
import click

from modules.classes import ListHandler, LoguruHandler
from modules.cfg_load import RootConfig
from modules.db_init import Proxy


# Disable "click text-line interface"
def secho(text, file=None, nl=None, err=None, color=None, **styles):
    pass


def echo(text, file=None, nl=None, err=None, color=None, **styles):
    pass


click.echo = echo
click.secho = secho


def rest_api(config: RootConfig, db_session: sessionmaker, sm_db_sem, sm_tui_buffer, sm_change_flag, sm_tui_refresh):
    log = logging.getLogger('werkzeug')
    list_handler = ListHandler(
        sm_tui_buffer, config.system.tui_text_line_buffer_size, sm_change_flag, sm_tui_refresh, log
    )
    list_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    loguru_handler = LoguruHandler(logger)
    loguru_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    log.addHandler(list_handler)
    log.addHandler(loguru_handler)

    app = Flask(__name__)

    @app.get("/proxy")
    def proxy():
        with sm_db_sem:
            with db_session.begin() as ses:
                good_all_proxy = ses.query(Proxy).filter(Proxy.ip_out.isnot(None)).all()
        return good_all_proxy

    app.run()


