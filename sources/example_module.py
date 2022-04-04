def get_proxy() -> list[{}, {}, ...]:

    result_list = [{
        'country_code_in': "BB",  # two-letter country code or None
        'ip_in': '1.2.3.4',
        'port_in': 4321,
        'type': 4
    }, {
        'country_code_in': "CC",
        'ip_in': '4.3.2.1',
        'port_in': 1234,
        'type': 5
    }]

    return result_list


if __name__ == "__main__":
    print(get_proxy())
    print(get_proxy.__annotations__)
