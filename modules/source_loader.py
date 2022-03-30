from sqlalchemy.orm.session import sessionmaker
from threading import Thread, Event, Timer
from datetime import datetime, timedelta
from operator import itemgetter
from loguru import logger
from pathlib import Path
import importlib.util

from modules.cfg_load import RootConfig
from modules.db_init import SourceTimer, Proxy

thread_timer = None


@logger.catch()
def source_loader(
        config: RootConfig, sm_db_sem, db_session: sessionmaker, sm_process_status, sm_new_proxy_event,
        sm_processes_id_list, sm_tui_buffer, sm_tui_change_flag, sm_tui_refresh, sm_timer_event
):
    global thread_timer
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

        thread_wait_event = Thread(
            target=wait_tui_event,
            args=(sm_timer_event, thread_unlock_event)
        )
        thread_wait_event.start()

        while sm_process_status.value:
            for source in sources_list:
                # 1. Check timer
                if not source.get("last_use", False):
                    with sm_db_sem:
                        with db_session(expire_on_commit=False) as ses:
                            source_db: SourceTimer = ses.query(SourceTimer).filter(
                                SourceTimer.name == source['name']
                            ).first()
                            if not source_db:
                                ses.add(SourceTimer(name=source['name']))
                                source_db: SourceTimer = ses.query(SourceTimer).filter(
                                    SourceTimer.name == source['name']
                                ).first()
                            if source_db.ts:
                                source["last_use"] = source_db.ts
                            ses.commit()
                ts_load = datetime.now() - timedelta(seconds=source['timer'])
                if not source.get("last_use", False) or ts_load > source.get("last_use", False):
                    # 2. Load source
                    source.update({"status": "NOW"})
                    source_list_update_event.set()
                    spec = importlib.util.spec_from_file_location("source_module", Path("sources", f"{source['name']}.py"))
                    source_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(source_module)
                    proxy_list: list = source_module.get_proxy(config.proxy.country_code_ignore_list)
                    load_count = len(proxy_list)
                    source.update({"load_proxy": load_count})
                    source_list_update_event.set()
                    logger.debug(f"Source: {source['name']} | Load: {load_count}")
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
                                ses.add_all([
                                    Proxy(**proxy) for proxy in proxy_list
                                ])
                                sm_new_proxy_event.set()
                    source.update({"write_proxy": len(proxy_list)})
                    logger.debug(f"Source: {source['name']} | Load: {load_count} | Write: {len(proxy_list)}")
                    source_list_update_event.set()
                    # 3. Update timer in DB
                    with sm_db_sem:
                        last_use = datetime.now()
                        with db_session() as ses:
                            source_db = ses.merge(source_db)
                            source_db.ts = last_use
                            ses.commit()
                    # 4. Update timer in dict
                    next_use = last_use + timedelta(seconds=source['timer'])
                    source.update({
                        "last_use": last_use,
                        "next_use": next_use,
                        "status": "LOADED"})
                    logger.debug(
                        f"Source: {source['name']} | Load: {load_count} | Write: {len(proxy_list)} | {last_use.isoformat(' ', 'seconds')}"
                    )
                    source_list_update_event.set()
                    time_to_next_load = (next_use - datetime.now()).seconds
                    logger.debug(f"Source {source['name']} will be checked in {time_to_next_load} seconds")
                else:
                    if not source.get('next_use'):
                        next_use = source['last_use'] + timedelta(seconds=source['timer'])
                        source.update({
                            "next_use": next_use})
                        source_list_update_event.set()
            # 5. Sorted sources_list from 'last_use' in source
            sources_list = sorted(sources_list, key=itemgetter('last_use'))
            second_timer = (datetime.now() - sources_list[0]['next_use']).seconds
            if sm_process_status.value:
                thread_timer = Timer(second_timer, thread_event_unlock, args=(thread_unlock_event, ))
                thread_timer.start()
                thread_unlock_event.wait()
                thread_unlock_event.clear()
                thread_timer.join()
                thread_timer = None
            else:
                break
        if not source_list_update_event.is_set(): source_list_update_event.set()
        thread_text_compositor.join()
        thread_wait_event.join()
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
    table_headers = ['Source name', 'Last use', 'Next use', 'Load proxy', 'Write proxy']
    name_length = len(table_headers[0])
    last_use_length = len(table_headers[1])
    next_use_length = len(table_headers[2])
    load_proxy_length = len(table_headers[3])
    write_proxy_length = len(table_headers[4])
    while sm_process_status.value:
        sm_tui_buffer[:] = []
        table_headers_string = f'{table_headers[0]:<{name_length}} ' \
                               f'{table_headers[1]:<{last_use_length}} ' \
                               f'{table_headers[2]:<{next_use_length}} ' \
                               f'{table_headers[3]:<{load_proxy_length}} ' \
                               f'{table_headers[4]:<{write_proxy_length}}'
        sm_tui_buffer.append(table_headers_string)
        for source in sources_list:
            prev_lens = (name_length, last_use_length, next_use_length, load_proxy_length, write_proxy_length)

            name_string, len_name_string = source['name'], len(source['name'])
            if source.get('last_use', None): last_use_string = source['last_use'].isoformat(' ', 'seconds')
            else: last_use_string = 'None'
            if source.get('next_use', None): next_use_string = source['next_use'].isoformat(' ', 'seconds')
            else: next_use_string = 'None'
            if source.get('load_proxy', None): load_string = str(source['load_proxy'])
            else: load_string = 'None'
            if source.get('write_proxy', None): write_string = str(source['write_proxy'])
            else: write_string = 'None'

            len_last_use_string = len(last_use_string)
            len_next_use_string = len(next_use_string)
            len_load_string = len(load_string)
            len_write_string = len(write_string)

            if name_length < len_name_string: name_length = len_name_string
            if last_use_length < len_last_use_string: last_use_length = len_last_use_string
            if next_use_length < len_next_use_string: next_use_length = len_next_use_string
            if load_proxy_length < len_load_string: load_proxy_length = len_load_string
            if write_proxy_length < len_write_string: write_proxy_length = len_write_string

            if prev_lens != (name_length, last_use_length, next_use_length, load_proxy_length):
                sm_tui_buffer[0] = f'{table_headers[0]:<{name_length}} ' \
                                   f'{table_headers[1]:<{last_use_length}} ' \
                                   f'{table_headers[2]:<{next_use_length}} ' \
                                   f'{table_headers[3]:<{load_proxy_length}} ' \
                                   f'{table_headers[4]:<{write_proxy_length}}'
            source_string = f'{name_string:<{name_length}} ' \
                            f'{last_use_string:<{last_use_length}} ' \
                            f'{next_use_string:<{next_use_length}} ' \
                            f'{load_string:<{load_proxy_length}} ' \
                            f'{write_string:<{write_proxy_length}}'
            sm_tui_buffer.append(source_string)
        if len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
            while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
                sm_tui_buffer.pop(-1)
        sm_tui_change_flag.value = True
        sm_tui_refresh.set()
        source_list_update_event.wait()
        source_list_update_event.clear()


@logger.catch()
def wait_tui_event(sm_timer_event, thread_unlock_event):
    global thread_timer

    sm_timer_event.wait()
    if thread_timer:
        thread_timer.cancel()
        thread_unlock_event.set()
