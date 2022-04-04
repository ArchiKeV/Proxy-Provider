# Proxy-Provider

is a service for downloading, checking and providing socks proxy servers.

<img height="" src="https://raw.githubusercontent.com/ArchiKeV/Proxy-Provider/develop/pp1.png" width="400"/><img height="" src="https://raw.githubusercontent.com/ArchiKeV/Proxy-Provider/develop/pp2.png" width="400"/>
<img height="" src="https://raw.githubusercontent.com/ArchiKeV/Proxy-Provider/develop/pp3.png" width="400"/><img height="" src="https://raw.githubusercontent.com/ArchiKeV/Proxy-Provider/develop/pp4.png" width="400"/>

## How to install:

#### Unix:

To download and run this project, you need to install `git`

1. Launch terminal in the folder for this project
2. Clone project repository - `git clone https://github.com/ArchiKeV/Proxy-Provider.git`
3. Go to project folder - `cd Proxy-Provider`
4. Allow execution of `init.sh` and `run.sh` files - `chmod + x init.sh run.sh`
5. Run `init.sh` for the first time - `./init.sh`

#### Windows:

To download and run this project, you need to install `git` and `python`

[Git](https://git-scm.com/download/win), [Python](https://www.python.org/downloads/windows/)

1. Launch terminal in the folder for this project  
2. Clone project repository - `git clone https://github.com/ArchiKeV/Proxy-Provider.git`
3. Go to project folder - `cd Proxy-Provider`
4. Run `init.bat` for the first time - `init.bat`



## How to run:

#### Unix:

1. Launch terminal in this project folder  
2. Run `run.sh` in a terminal every time you need to run a project - `./run.sh`  
3. Use the visual text interface in the terminal and get tested proxy servers at `127.0.0.1:5000/proxy`
4. Run `run.sh` in a terminal every time you need to run a project - `./run.sh`

#### Windows:

1. Launch terminal in this project folder  
2. Run `run.bat` for the first time - `run.bat`  
3. Use the visual text interface in the terminal and get tested proxy servers at `127.0.0.1:5000/proxy`
4. The first run will create a basic `config.json`, use that to configure

## Architecture:

#### Input data:

The input data for the service is described in the configuration file `config.json` created when the service is first started. It, among other things, describes all the used sources of proxy servers, their configuration will be discussed below.

#### Sources of proxy servers:

Proxy sources are provided as a Python 3 module located in the `./sources` directory. An example module is described in `./sources/example_module.py`. Such a module should independently obtain lists of proxy servers and return a list of dictionaries in the `get_proxy()` function:

```python
[
    {
        'country_code_in': "BB", # two-letter country code or None
        'ip_in': '1.2.3.4',      # string
        'port_in': 4321,         # integer
        'type': 4                # integer - socks proxy type (4 or 5)
    },
    {
        'country_code_in': None,
        'ip_in': '4.3.2.1',
        'port_in': 1234,
        'type': 5
    }
]
```

Parameter `country_code_in` - ISO code of the country of entry into the proxy server, the parameter is optional, but desirable. This setting is used to filter out unwanted provider countries. The list of unwantedm countries is described in config.json (details below). If there is no information about the country of entry, the parameter should be filled with the value `None`. 

#### Checking proxy servers:

Available proxies are checked by visiting a site with connection information through the proxy server. From this information, data on the Country of exit and the exit IP address are taken.

#### Provision of verified proxies:

Verified proxies are provided by the FLASK server as a REST API (currently only getting tested servers is available).

#### Configuration file:

The configuration file consists of three sections - `db`, `proxy`, `system`. Each section is responsible for its part of the settings.

###### DB:

`db_type` - db type (currently|default - `sqlite`, others in the future)

`settings.filepath` - db name (default - `proxy_provider_db.sqlite`)

`settings.concurrent_slots` - Num of concurrent db access slots (sqlite default - `1`)

###### Proxy:

`country_code_ignore_list` - List of 2-letter codes of unwanted countries whose proxies will not be added to the database. Default - `["IR", ]`

`sources` - List of proxy server source dictionaries:

`    "name": str` - Module name and display name, DO NOT end with `.py` 

`    "timer": int` - Source reload timer, in seconds. It should be set based on the source update frequency and large enough so as not to be aggressive towards the source server (so as not to be banned)

`checkup_timers.active_server_check_period_in_hours` - Timer in hours, for working servers  

`checkup_timers.inactive_server_check_period_in_hours` -Timer in hours, for not working servers (currently not in use)  

`timeouts.connection_timeout` - Server connection timeout during health check (in seconds)  

`timeouts.read_timeout` - Server read timeout during health check (in seconds)  

`num_of_simultaneous_checks` - The number of simultaneously scanned servers, the more simultaneous scans, the faster all servers will be scanned (`5` - default)

###### System:

`tui_text_line_buffer_size` - String buffer for TUI (default - `500`)  

`debug` - Debug mode (default - `False`). Currently affects the behavior of sqlalchemy and does not affect logs
