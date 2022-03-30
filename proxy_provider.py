from multiprocessing import Process, Manager
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy import create_engine
from loguru import logger
import datetime
import logging
import os

from modules.classes import LoguruHandler
from modules.cfg_load import load_cfg
from modules.db_init import base
from modules.rest_api import rest_api
from modules.source_loader import source_loader
from modules.proxy_tester import proxy_tester

# Loguru config .isoformat(' ', 'seconds')
logging_file_name = f"proxy_provider_{datetime.datetime.now()}.log"
logger.remove()
logger.add(
    sink=logging_file_name,
    format="{time} {process} {level} {name} {message}",
    enqueue=True,
    level="TRACE",
    rotation="1000 KB",
    compression='zip'
)


# Logging to loguru config
log = logging.getLogger('sqlalchemy.engine.Engine')
loguru_handler = LoguruHandler(logger)
loguru_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
log.addHandler(loguru_handler)


@logger.catch()
def main():
    # Load config
    config = load_cfg()

    # Read or Create database
    if config.db.db_type == 'sqlite':
        db_path = config.db.settings.filepath
        base_path = os.path.dirname(os.path.realpath(__file__))
        db_path = os.path.join(base_path, db_path)
        engine = create_engine(f'sqlite:///{db_path}', echo=True)
    else:
        engine = None
        logger.error('DB type is not supported')
        exit()
    base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine)

    # Start multiprocessor configuration
    menu_items_and_processes_roles = [
        'Rest API',
        'Source Loader',
        'Proxy Tester',
        'Exit'
    ]
    with Manager() as SM:
        # Common variables for child processes
        sm_db_sem = SM.Semaphore(config.db.settings.concurrent_slots)
        sm_processes_id_list = SM.list()
        sm_process_status = SM.Value(bool, True)
        sm_new_proxy_event = SM.Event()

        # Variables for TUI process
        sm_tui_refresh = SM.Event()
        sm_dict_for_buffers = SM.dict()
        sm_dict_for_change_flags = SM.dict()

        process_list = []
        for role in menu_items_and_processes_roles:
            if role == 'Rest API':
                sm_tui_buffer = SM.list()
                sm_dict_for_buffers.update({role: sm_tui_buffer})
                sm_change_flag = SM.Value(bool, False)
                sm_dict_for_change_flags.update({role: sm_change_flag})

                rest_api_p = Process(target=rest_api, args=(
                    config,
                    db_session,
                    sm_db_sem,
                    sm_tui_buffer,
                    sm_change_flag,
                    sm_tui_refresh
                ))
                process_list.append(rest_api_p)
                rest_api_p.start()
            elif role == 'Source Loader':
                sm_tui_buffer = SM.list()
                sm_dict_for_buffers.update({role: sm_tui_buffer})
                sm_change_flag = SM.Value(bool, False)
                sm_dict_for_change_flags.update({role: sm_change_flag})

                p = Process(target=source_loader, args=(
                    config,
                    sm_db_sem,
                    db_session,
                    sm_process_status,
                    sm_new_proxy_event,
                    sm_processes_id_list,
                    sm_tui_buffer,
                    sm_change_flag,
                    sm_tui_refresh
                ))
                process_list.append(p)
                p.start()
            elif role == 'Proxy Tester':
                sm_tui_buffer = SM.list()
                sm_dict_for_buffers.update({role: sm_tui_buffer})
                sm_change_flag = SM.Value(bool, False)
                sm_dict_for_change_flags.update({role: sm_change_flag})

                p = Process(target=proxy_tester, args=(
                    config,
                    sm_db_sem,
                    db_session,
                    sm_process_status,
                    sm_new_proxy_event,
                    sm_processes_id_list,
                    sm_tui_buffer,
                    sm_change_flag,
                    sm_tui_refresh
                ))
                process_list.append(p)
                p.start()
            elif role == 'Exit':
                sm_tui_buffer = SM.list()
                sm_dict_for_buffers.update({role: sm_tui_buffer})
                sm_change_flag = SM.Value(bool, False)
                sm_dict_for_change_flags.update({role: sm_change_flag})
        import modules.tui as tui
        curses_tui_p = Process(target=tui.curses_tui, args=(
            sm_process_status, sm_dict_for_buffers, sm_dict_for_change_flags, sm_tui_refresh,
            menu_items_and_processes_roles, rest_api_p, sm_processes_id_list
        ))
        curses_tui_p.start()
        for p in process_list:
            p.join()
        curses_tui_p.join()


if __name__ == "__main__":
    main()
