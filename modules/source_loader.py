from sqlalchemy.orm.session import sessionmaker
from threading import Thread, Event, Timer
from datetime import datetime, timedelta
from operator import itemgetter
from loguru import logger
import importlib.util

from modules.cfg_load import RootConfig
from modules.db_init import SourceTimer, Proxy


@logger.catch()
def source_loader(config: RootConfig, sm_db_sem, db_session: sessionmaker, sm_process_status, sm_new_proxy_event,
                  sm_processes_id_list, sm_tui_buffer, sm_tui_change_flag, sm_tui_refresh):
    sm_processes_id_list.append('source_loader')

    sources_list = [source_in_cfg.dict() for source_in_cfg in config.proxy.sources]
    if not sources_list:
        sm_tui_buffer.append('No source loaded')
        sm_tui_change_flag.value = True
        sm_tui_refresh.set()
        sm_processes_id_list.remove('source_loader')
    else:
        source_list_update_event = Event()
        thread_unlock_event = Event()
        thread_unlock_event.set()

        thread_text_compositor = Thread(
            target=text_compositor,
            args=(
                sm_process_status,
                sm_tui_buffer,
                config,
                sm_tui_change_flag,
                sm_tui_refresh,
                sources_list,
                source_list_update_event
                )
        )
        thread_text_compositor.start()

        while sm_process_status.value:
            logger.debug('In "source_loader", start "while"')
            for source in sources_list:
                # 1. Check timer
                if not source.get("last_use", False):
                    with sm_db_sem:
                        with db_session.begin() as ses:
                            source_db: SourceTimer = ses.query(SourceTimer).filter(SourceTimer.name == source.name).first()
                            if not source_db:
                                ses.add(SourceTimer(name=source['name']))
                                source_db: SourceTimer = ses.query(SourceTimer).filter(
                                    SourceTimer.name == source.name
                                ).first()
                            logger.debug(f"{type(source_db.ts)} {source_db.ts}")
                            if source_db.ts:
                                source["last_use"] = source_db.ts
                ts_load = datetime.now() - timedelta(seconds=source.timer)
                if not source.get("last_use", False) or ts_load > source.get("last_use", False):
                    # 2. Load source
                    source.update({"status": "NOW"})
                    source_list_update_event.set()
                    spec = importlib.util.spec_from_file_location("source_module", source['module_path'])
                    source_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(source_module)
                    proxy_list: list = source_module.get_proxy(config.proxy.country_code_ignore_list)
                    source.update({"load_proxy": len(proxy_list)})
                    source_list_update_event.set()
                    logger.debug(f"Source: {source.name} | Load: {len(proxy_list)}")
                    with sm_db_sem:
                        with db_session.begin() as ses:
                            delete_proxy_list = []
                            for proxy in proxy_list:
                                old_proxy = ses.query(Proxy).filter(
                                    Proxy.ip_in == proxy["ip_in"],
                                    Proxy.port_in == proxy["port_in"]
                                ).first()
                                if old_proxy:
                                    delete_proxy_list.append(proxy)
                            for d_proxy in delete_proxy_list:
                                proxy_list.remove(d_proxy)
                            if len(proxy_list) > 0:
                                proxy_write = ses.add_all([
                                    Proxy(**proxy) for proxy in proxy_list
                                ])
                                if proxy_write > 0:
                                    sm_new_proxy_event.set()
                    source.update({"write_proxy": proxy_write})
                    logger.debug(f"Source: {source.name} | Load: {len(proxy_list)} | Write: {proxy_write}")
                    source_list_update_event.set()
                    # 3. Update timer in DB
                    with sm_db_sem:
                        last_use = datetime.now()
                        with db_session.begin():
                            source_db.ts = last_use
                    # 4. Update timer in dict
                    source.update({"last_use": last_use})
                    logger.debug(f"Source: {source.name} | Load: {len(proxy_list)} | Write: {proxy_write} | {last_use}")
                    source_list_update_event.set()
                # 5. Sorted sources_list from 'last_use' in source
                time_to_next_load = ((source['last_use'] + timedelta(seconds=source['timer'])) - datetime.now()).seconds
                logger.debug(f"Source {source['name']}will be checked in {time_to_next_load} seconds")
            sources_list = sorted(sources_list, key=itemgetter('last_use'))
            second_timer = (datetime.now() - sources_list[0]['last_use']).seconds
            thread_unlock_event.clear()
            t = Timer(second_timer, thread_event_unlock, args=(thread_unlock_event, ))
            t.start()
            thread_unlock_event.wait()
            t.join()
        thread_text_compositor.join()
        sm_new_proxy_event.set()
        sm_processes_id_list.remove('source_loader')


@logger.catch()
def thread_event_unlock(thread_unlock_event):
    thread_unlock_event.set()


@logger.catch()
def text_compositor(
        sm_process_status, sm_tui_buffer, config, sm_tui_change_flag, sm_tui_refresh, sources_list,
        source_list_update_event
):
    table_headers = ['Source name', 'Last use', 'Next use', 'Last n proxy']
    name_length = len(table_headers[0])
    last_use_length = len(table_headers[1])
    next_use_length = len(table_headers[2])
    last_n_proxy_length = len(table_headers[3])
    while sm_process_status.value:
        sm_tui_buffer[:] = []
        table_headers_string = f'{table_headers[0]:<{name_length}} ' \
                               f'{table_headers[1]:<{last_use_length}} ' \
                               f'{table_headers[2]:<{next_use_length}} ' \
                               f'{table_headers[3]:<{last_n_proxy_length}}'
        sm_tui_buffer.append(table_headers_string)
        for source in sources_list:
            prev_lens = (name_length, last_use_length, next_use_length, last_n_proxy_length)
            if len(source['name']) > name_length:
                name_length = len(source['name'])
            if len(str(source['last_use_ts'])) > last_use_length:
                last_use_length = len(str(source['last_use_ts']))
            if not source.get("next_use", None):
                source.update({'next_use': None})
            if len(str(source['next_use'])) > next_use_length:
                next_use_length = len(str(source['next_use']))
            if not source.get("last_n_proxy", None):
                source.update({'last_n_proxy': None})
            if len(str(source['last_n_proxy'])) > last_n_proxy_length:
                last_n_proxy_length = len(str(source['last_n_proxy']))
            if prev_lens != (name_length, last_use_length, next_use_length, last_n_proxy_length):
                sm_tui_buffer[0] = f'{table_headers[0]:<{name_length}} ' \
                                   f'{table_headers[1]:<{last_use_length}} ' \
                                   f'{table_headers[2]:<{next_use_length}} ' \
                                   f'{table_headers[3]:<{last_n_proxy_length}}'
            source_string = f'{source["name"]:<{name_length}} ' \
                            f'{str(source["last_use_ts"]):<{last_use_length}} ' \
                            f'{str(source["next_use"]):<{next_use_length}} ' \
                            f'{str(source["last_n_proxy"]):<{last_n_proxy_length}}'
            sm_tui_buffer.append(source_string)
        if len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
            while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
                sm_tui_buffer.pop(-1)
        sm_tui_change_flag.value = True
        sm_tui_refresh.set()
        source_list_update_event.wait()
        source_list_update_event.clear()

