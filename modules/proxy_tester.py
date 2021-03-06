from sqlalchemy.orm.session import sessionmaker
from multiprocessing import Process, Semaphore
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from loguru import logger

from modules.cfg_load import RootConfig
from modules.db_init import Proxy


@logger.catch()
def proxy_tester(
        config: RootConfig, sm_db_sem, db_session: sessionmaker, sm_process_status, sm_new_proxy_event,
        sm_processes_id_list, sm_tui_buffer, sm_change_flag, sm_tui_refresh
):
    sm_processes_id_list.append('proxy_tester_main')

    sources_list = [source_in_cfg.dict() for source_in_cfg in config.proxy.sources]
    if not sources_list:
        sm_processes_id_list.remove('proxy_tester_main')
        return

    with sm_db_sem:
        with db_session(expire_on_commit=False) as ses:
            not_tested_proxy_servers = ses.query(Proxy).filter(or_(
                Proxy.ip_out.is_(None),
                and_(Proxy.ip_out.isnot(None), or_(
                    Proxy.status_ts.is_(None),
                    Proxy.status_ts > datetime.now() +
                    timedelta(hours=config.proxy.checkup_timers.active_server_check_period_in_hours)
                ))
            )).all()
            ses.commit()
    while sm_process_status.value:
        if not_tested_proxy_servers:
            # Proxy testing
            processes_semaphore = Semaphore(config.proxy.num_of_simultaneous_checks)
            buffer_semaphore = Semaphore()
            process_list = []
            for proxy in not_tested_proxy_servers:
                if not sm_process_status.value:
                    break
                processes_semaphore.acquire()
                for num in range(len(process_list)):
                    if process_list[num].exitcode is not None:
                        process_list[num].join()
                        process_list.pop(num)
                        break
                p = Process(target=check_and_update_new_proxy, args=(
                    proxy,
                    config,
                    db_session,
                    sm_db_sem,
                    processes_semaphore,
                    sm_processes_id_list,
                    sm_tui_buffer,
                    sm_change_flag,
                    sm_tui_refresh,
                    buffer_semaphore
                ))
                process_list.append(p)
                p.start()
            for p in process_list:
                p.join()
        if sm_process_status.value:
            sm_new_proxy_event.wait()
            sm_new_proxy_event.clear()
            # Checking for new proxies
            if sm_process_status.value:
                with sm_db_sem:
                    with db_session.begin() as ses:
                        not_tested_proxy_servers = ses.query(Proxy).filter(Proxy.ip_out.is_(None))
    sm_processes_id_list.remove('proxy_tester_main')


@logger.catch()
def check_and_update_new_proxy(
        proxy: Proxy, config: RootConfig, db_session: sessionmaker, sm_db_sem, processes_semaphore,
        sm_processes_id_list, sm_tui_buffer, sm_change_flag, sm_tui_refresh, buffer_semaphore
):
    import requests
    import random

    sm_processes_id_list.append('proxy_tester_child')
    logger.info(f'Check {proxy.ip_in} {proxy.port_in} {proxy.country_code_in}')

    connection_timeout = config.proxy.timeouts.connection_timeout
    read_timeout = config.proxy.timeouts.read_timeout

    url_with_captcha = [
        "https://freegeoip.app/json",
        "https://ifconfig.co/json",
        "https://ifconfig.io/all.json",
        "https://api.ip.sb/geoip",
        "https://api.hostip.info/get_json.php"
    ]
    urls = [
        "https://ipwhois.app/json/",
        "https://ip-api.io/json",
        "https://ipinfo.io/json",
        "https://wtfismyip.com/json"
    ]
    url = random.choice(urls)
    with buffer_semaphore:
        sm_tui_buffer.append(f'{proxy.ip_in} {proxy.port_in} NOW')
        while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
            sm_tui_buffer.pop(0)
    sm_change_flag.value = True
    sm_tui_refresh.set()
    socks_proxy = {
        "http": f"socks{proxy.type}://{proxy.ip_in}:{proxy.port_in}",
        "https": f"socks{proxy.type}://{proxy.ip_in}:{proxy.port_in}"
    }
    try:
        response = requests.get(url, proxies=socks_proxy, timeout=(connection_timeout, read_timeout))
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout):
        logger.info(f'CT|CE|RT when checking {proxy.ip_in} {proxy.port_in}')
        with buffer_semaphore:
            sm_tui_buffer.remove(f'{proxy.ip_in} {proxy.port_in} NOW')
            sm_tui_buffer.append(f'{proxy.ip_in} {proxy.port_in} BAD')
            while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
                sm_tui_buffer.pop(0)
        sm_change_flag.value = True
        sm_tui_refresh.set()
        with sm_db_sem:
            with db_session.begin() as ses:
                proxy = ses.merge(proxy)
                ses.delete(proxy)
        sm_processes_id_list.remove('proxy_tester_child')
        processes_semaphore.release()
        return
    if response.status_code == 200:
        proxy_dict = response.json()
        with sm_db_sem:
            with db_session.begin() as ses:
                proxy = ses.merge(proxy)
                if url == "https://ifconfig.co/json":
                    proxy.ip_out = proxy_dict['ip']
                    proxy.country_code_out = proxy_dict['country_iso']
                elif url in [
                    "https://freegeoip.app/json", "https://ipwhois.app/json/", "https://ip-api.io/json",
                    "https://ifconfig.io/all.json", "https://api.ip.sb/geoip", "https://api.hostip.info/get_json.php"
                ]:
                    proxy.ip_out = proxy_dict['ip']
                    proxy.country_code_out = proxy_dict['country_code']
                elif url == "https://ipinfo.io/json":
                    proxy.ip_out = proxy_dict['ip']
                    proxy.country_code_out = proxy_dict['country']
                elif url == "https://wtfismyip.com/json":
                    proxy.ip_out = proxy_dict['YourFuckingIPAddress']
                    proxy.country_code_out = proxy_dict['YourFuckingCountryCode']
                proxy.status_ts = datetime.now()
                logger.info(f'GOOD proxy {proxy.ip_in} {proxy.port_in} {proxy.ip_out} via {url}')
                with buffer_semaphore:
                    sm_tui_buffer.remove(f'{proxy.ip_in} {proxy.port_in} NOW')
                    sm_tui_buffer.append(f'{proxy.ip_in} {proxy.port_in} GOOD')
                    while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
                        sm_tui_buffer.pop(0)
        sm_change_flag.value = True
        sm_tui_refresh.set()
    else:
        with open(
                f'{response.status_code}_{url.split("/")[2]}_{proxy.ip_in.replace(".", "_")}_{proxy.port_in}.html', 'wb'
        ) as proxy_file:
            proxy_file.write(response.content)
        with sm_db_sem:
            with db_session.begin() as ses:
                proxy = ses.merge(proxy)
                ses.delete(proxy)
        logger.info(f'Error in file when checking {proxy.ip_in} {proxy.port_in}')
        with buffer_semaphore:
            sm_tui_buffer.remove(f'{proxy.ip_in} {proxy.port_in} NOW')
            sm_tui_buffer.append(f'{proxy.ip_in} {proxy.port_in} BAD')
            while len(sm_tui_buffer) > config.system.tui_text_line_buffer_size:
                sm_tui_buffer.pop(0)
        sm_change_flag.value = True
        sm_tui_refresh.set()
    sm_processes_id_list.remove('proxy_tester_child')
    processes_semaphore.release()
