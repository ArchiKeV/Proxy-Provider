from loguru import logger
from io import BytesIO
import requests


@logger.catch()
def get_proxy(country_code_ignore_list: list[str]) -> list[{}, {}, ...]:
    proxy_all = []
    response = requests.get('https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt')
    f = BytesIO(response.content)
    for ip_port_string in f.read().decode().splitlines():
        ip, port = ip_port_string.split(':')
        proxy_all.append({
            'country_code_in': None,
            'ip_in': ip,
            'port_in': int(port),
            'type': 4
        })
    return proxy_all


if __name__ == "__main__":
    print(get_proxy())
